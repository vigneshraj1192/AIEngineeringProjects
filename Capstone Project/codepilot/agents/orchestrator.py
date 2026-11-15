"""Orchestrator Agent: Root coordinator running planning, issue polling, and subagent spawning."""

import time
import threading
from typing import Dict, Any, List, Optional
from pathlib import Path

from deepagents import create_deep_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.chat_models import BaseChatModel

from codepilot.config import config
from codepilot.state import TaskStatus, TaskType, IssueItem, TaskWorkingMemory
from codepilot.github.client import github_client
from codepilot.github.toolkit import get_github_tools
from codepilot.skills.loader import skills
from codepilot.memory.working import working_memory
from codepilot.memory.episodic import episodic_memory
from codepilot.memory.semantic import semantic_memory
from codepilot.sandbox.local_sandbox import LocalSandbox
from codepilot.agents.repo_explorer import RepoExplorerAgent
from codepilot.agents.coder import CoderAgent
from codepilot.agents.pr_agent import PRAgent
from codepilot.tui.event_bus import event_bus, EventType

ORCHESTRATOR_SYSTEM_PROMPT = """
You are the Orchestrator Agent for CodePilot, an autonomous coding platform at DevStream Labs.
Your core mission is to autonomously resolve GitHub issues and user coding tasks:
1. Poll GitHub issues and classify tasks into bug_fix, feature_addition, dependency_update, documentation, or config_change.
2. Formulate execution plans using the write_todos tool.
3. Spawn specialist subagents:
   - Repo Explorer: analyze repo map and locate top-K relevant files
   - Coder Agent: make surgical edits in sandboxed local environment
   - Test Agent: write tests and verify solution
   - PR Agent: create branches, structured commits, and open pull requests
4. Never perform unsafe or ambiguous operations without human approval.
"""

class OrchestratorAgent:
    """Root agent managing the full task lifecycle and subagent delegation."""

    def __init__(self, repo_path: Optional[Path] = None, model: Optional[BaseChatModel] = None):
        target_dir = repo_path or ((config.base_dir / "sample_repo") if (config.base_dir / "sample_repo").exists() else config.base_dir)
        self.repo_path = Path(target_dir).resolve()
        self.model = model or self._init_model()
        self.in_progress_issues: set[int] = set()
        self.polling_active = False
        self._polling_thread: Optional[threading.Thread] = None

        # DeepAgents root coordinator initialization
        try:
            self.deep_agent = create_deep_agent(
                model=self.model,
                system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
                tools=get_github_tools(),
            )
            event_bus.log("Orchestrator", "Initialized Root DeepAgent with planning prompt and GitHub tools", level="INFO")
        except Exception as e:
            event_bus.log("Orchestrator", f"Warning initializing DeepAgent wrapper ({e}); using direct model orchestration", level="WARNING")
            self.deep_agent = None

        # Check startup episodic memory for recently failed issues
        self.recently_failed_issues = episodic_memory.get_recently_failed_issue_numbers(limit_sessions=3)
        if self.recently_failed_issues:
            event_bus.log("Orchestrator", f"Episodic memory: will skip recently failed issues: {self.recently_failed_issues}", level="INFO")

    def _init_model(self) -> BaseChatModel:
        """Initialize LLM model with fallback handling."""
        try:
            return ChatGoogleGenerativeAI(
                model=config.model_name,
                temperature=config.temperature,
                max_retries=2,
            )
        except Exception:
            return None

    def classify_task(self, issue: IssueItem) -> TaskType:
        """Classify task into bug_fix, feature_addition, dependency_update, documentation, config_change."""
        title_body = f"{issue.title} {issue.body}".lower()
        labels = [l.lower() for l in issue.labels]

        # Check documentation first
        if any(l in labels for l in ("documentation", "docs")) or "readme" in title_body or "documentation" in title_body or "docs" in title_body:
            return TaskType.DOCUMENTATION
        # Check dependencies
        elif any(l in labels for l in ("dependencies", "dependency", "upgrade", "bump")) or "upgrade" in title_body or "bump" in title_body or "dependency" in title_body:
            return TaskType.DEPENDENCY_UPDATE
        # Check feature addition
        elif any(l in labels for l in ("feature", "enhancement", "addition")) or "add" in title_body or "new feature" in title_body:
            return TaskType.FEATURE_ADDITION
        # Check config change
        elif any(l in labels for l in ("config", "configuration", "docker", "ci/cd")) or "config" in title_body:
            return TaskType.CONFIG_CHANGE
        # Default to bug fix
        else:
            return TaskType.BUG_FIX

    def score_complexity(self, issue: IssueItem) -> int:
        """Bonus Challenge: Score issue complexity from 1 to 10."""
        if issue.complexity_score is not None:
            return issue.complexity_score

        title_body = f"{issue.title} {issue.body}".lower()
        if "rewrite" in title_body or "architecture" in title_body or "consensus" in title_body:
            score = 10
        elif "add" in title_body and "service" in title_body:
            score = 6
        elif "upgrade" in title_body:
            score = 4
        elif "docs" in title_body or "readme" in title_body:
            score = 2
        else:
            score = 3
        
        issue.complexity_score = score
        return score

    def process_issue(self, issue: IssueItem) -> TaskStatus:
        """
        Execute the Orchestrator state machine for a single issue:
        TRIAGED → EXPLORING → IMPLEMENTING → TESTING → PR_OPENED → DONE | FAILED
        """
        # Exclude if already in progress or recently failed in episodic memory
        if issue.number in self.in_progress_issues:
            event_bus.log("Orchestrator", f"Issue #{issue.number} is already in progress; skipping", level="DEBUG")
            return TaskStatus.PENDING

        if issue.number in self.recently_failed_issues:
            event_bus.log("Orchestrator", f"Issue #{issue.number} failed in recent session; skipping to avoid churn", level="WARNING")
            return TaskStatus.SKIPPED

        # Complexity triage check
        complexity = self.score_complexity(issue)
        if complexity > config.complexity_threshold:
            event_bus.log(
                "Orchestrator",
                f"Skipping Issue #{issue.number}: Complexity score {complexity}/10 exceeds threshold ({config.complexity_threshold})",
                level="WARNING"
            )
            return TaskStatus.SKIPPED

        self.in_progress_issues.add(issue.number)

        # 1. State: TRIAGED
        task_type = self.classify_task(issue)
        assigned_skill = skills.load(task_type)
        memory = working_memory.initialize_task(issue=issue, task_type=task_type)
        memory.skill_name = assigned_skill.name
        memory.status = TaskStatus.TRIAGED

        event_bus.emit(EventType.TASK_STATE_CHANGED, memory.model_dump())
        event_bus.log(
            "Orchestrator",
            f"TRIAGED Issue #{issue.number} -> Type: {task_type.value} | Skill: {assigned_skill.name}",
            level="INFO"
        )

        try:
            # 2. State: EXPLORING (Spawn Repo Explorer Agent)
            memory.status = TaskStatus.EXPLORING
            memory.active_agent = "RepoExplorer"
            event_bus.emit(EventType.TASK_STATE_CHANGED, memory.model_dump())
            
            explorer = RepoExplorerAgent(self.repo_path, model=self.model)
            exploration = explorer.explore(
                task_description=f"{issue.title}\n{issue.body}",
                top_k=config.top_k_relevant_files,
                strategy=config.retrieval_strategy
            )
            memory.relevant_files = exploration["relevant_files"]

            # Query Semantic Memory for top-3 relevant past lessons
            past_lessons = semantic_memory.retrieve_relevant_lessons(
                repository=config.github_repository,
                query=f"{issue.title} {issue.body}",
                task_type=task_type.value,
                top_k=3
            )
            lessons_prompt = semantic_memory.format_lessons_for_prompt(past_lessons)
            event_bus.log("Orchestrator", f"Injected {len(past_lessons)} past lessons from Semantic Memory", level="DEBUG")

            # 3. State: IMPLEMENTING (Spawn Coder Agent in Local Sandbox)
            memory.status = TaskStatus.IMPLEMENTING
            memory.active_agent = "Coder"
            event_bus.emit(EventType.TASK_STATE_CHANGED, memory.model_dump())

            sandbox = LocalSandbox(
                task_id=memory.task_id,
                source_repo=self.repo_path,
                relevant_files=memory.relevant_files
            )
            memory.sandbox_path = str(sandbox.sandbox_dir)

            coder = CoderAgent(sandbox=sandbox, model=self.model)
            coder_success = coder.implement(
                memory=memory,
                skill=assigned_skill,
                past_lessons_prompt=lessons_prompt
            )

            # 4. State: TESTING verification
            memory.status = TaskStatus.TESTING
            memory.active_agent = "TestAgent"
            event_bus.emit(EventType.TASK_STATE_CHANGED, memory.model_dump())

            if not coder_success or not memory.test_passed:
                raise RuntimeError(f"Sandbox verification failed after {memory.retry_count} retries.")

            # 5. State: PR_OPENED (Spawn PR Agent)
            memory.status = TaskStatus.PR_OPENED
            memory.active_agent = "PR_Agent"
            event_bus.emit(EventType.TASK_STATE_CHANGED, memory.model_dump())

            pr_agent = PRAgent()
            pr_agent.create_pr_for_task(memory)

            # 6. State: DONE
            memory.status = TaskStatus.DONE
            memory.end_time = time.time()
            event_bus.emit(EventType.TASK_STATE_CHANGED, memory.model_dump())
            event_bus.log("Orchestrator", f"Task DONE for Issue #{issue.number}! PR: {memory.pr_url}", level="INFO")

            # Record in Semantic Memory (persistent lessons learned)
            semantic_memory.record_lesson(
                repository=config.github_repository,
                issue_number=issue.number,
                issue_title=issue.title,
                task_type=task_type.value,
                files_modified=memory.relevant_files,
                approach=f"Applied {assigned_skill.name} workflow and verified all tests pass in local sandbox."
            )

            # Record in Episodic Memory (session records)
            episodic_memory.record_task_outcome(memory)

            return TaskStatus.DONE

        except Exception as e:
            memory.status = TaskStatus.FAILED
            memory.end_time = time.time()
            memory.error_message = str(e)
            event_bus.emit(EventType.TASK_STATE_CHANGED, memory.model_dump())
            event_bus.log("Orchestrator", f"Task FAILED for Issue #{issue.number}: {e}", level="ERROR")

            # Record failure in Episodic Memory
            episodic_memory.record_task_outcome(memory)
            self.recently_failed_issues.add(issue.number)
            return TaskStatus.FAILED

        finally:
            if issue.number in self.in_progress_issues:
                self.in_progress_issues.remove(issue.number)
            # Clear working memory
            working_memory.clear()

    def start_polling(self, interval_seconds: Optional[int] = None) -> None:
        """Start the background GitHub issue polling loop."""
        interval = interval_seconds or config.poll_interval_seconds
        self.polling_active = True

        def _poll_worker():
            event_bus.log("Orchestrator", f"Started GitHub polling loop (interval: {interval}s)", level="INFO")
            while self.polling_active:
                try:
                    issues = github_client.list_issues(state="open")
                    event_bus.emit(EventType.ISSUE_LIST_UPDATED, {
                        "issues": [i.model_dump() for i in issues]
                    })
                    
                    # Process available issue
                    for issue in issues:
                        if not self.polling_active:
                            break
                        if issue.number not in self.in_progress_issues and issue.number not in self.recently_failed_issues:
                            self.process_issue(issue)
                            break
                except Exception as e:
                    event_bus.log("Orchestrator", f"Polling error: {e}", level="ERROR")

                time.sleep(interval)

        self._polling_thread = threading.Thread(target=_poll_worker, daemon=True)
        self._polling_thread.start()

    def stop_polling(self) -> None:
        """Stop polling loop and persist session summary in Episodic Memory."""
        self.polling_active = False
        summary = episodic_memory.save_session_summary()
        event_bus.log("Orchestrator", f"Session saved to episodic memory ({summary.total_tasks} tasks recorded)", level="INFO")

    def execute_manual_task(self, task_description: str) -> TaskStatus:
        """Execute a free-form coding task entered by user via TUI '[i] New task' shortcut."""
        ad_hoc_issue = IssueItem(
            number=999,
            title=task_description[:50],
            body=task_description,
            labels=["manual-task"],
            state="open",
            author="engineer-user",
            complexity_score=3,
        )
        return self.process_issue(ad_hoc_issue)
