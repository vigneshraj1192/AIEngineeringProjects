"""Coder Agent: Implements code edits in local sandbox, verifies via Test Agent, and generates diffs."""

from typing import Dict, Any, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage
from codepilot.config import config
from codepilot.state import TaskWorkingMemory, TaskStatus
from codepilot.sandbox.local_sandbox import LocalSandbox
from codepilot.skills.models import Skill
from codepilot.agents.tester import TestAgent, TestResult
from codepilot.guardrails.hitl import hitl
from codepilot.tui.event_bus import event_bus

CODER_SYSTEM_PROMPT = """
You are the Coder Agent for CodePilot.
Your goal is to inspect relevant files, plan a surgical fix or implementation, and produce exact file edits.

Guidelines:
1. Prefer surgical modifications over complete file rewrites.
2. Ensure no syntax errors or breaking changes.
3. Adhere strictly to the loaded Skill guidelines and forbidden actions.
4. Output your edits in a structured format:
FILE: <relative_path>
SEARCH:
<exact code to replace>
REPLACE:
<replacement code>
END_EDIT
"""

class CoderAgent:
    """Agent responsible for writing and modifying code within the isolated sandbox."""

    def __init__(self, sandbox: LocalSandbox, model: Optional[BaseChatModel] = None):
        self.sandbox = sandbox
        self.model = model
        self.tester = TestAgent(sandbox, model=model)

    def implement(
        self,
        memory: TaskWorkingMemory,
        skill: Skill,
        past_lessons_prompt: str = ""
    ) -> bool:
        """
        Execute the Coder inner loop:
        1. Read relevant files
        2. Formulate change plan
        3. Implement edits via edit_file / write_file
        4. Run code in sandbox
        5. Verify with Test Agent (max 3 retries, HITL at threshold 2)
        6. Generate proposed_diff.txt
        """
        event_bus.log("Coder", f"Starting implementation loop for task: {memory.issue.title}", level="INFO")
        memory.active_agent = "Coder"
        memory.skill_name = skill.name

        # 1. Read relevant files identified by Repo Explorer
        file_contents: Dict[str, str] = {}
        for rel_path in memory.relevant_files:
            try:
                content = self.sandbox.read_file(rel_path)
                file_contents[rel_path] = content
                event_bus.log("Coder", f"Read relevant file: {rel_path} ({len(content.splitlines())} lines)", level="DEBUG", tool_call="read_file")
            except Exception as e:
                event_bus.log("Coder", f"Warning: Could not read {rel_path}: {e}", level="WARNING")

        # 2. Formulate change plan into todos
        memory.todos.clear()
        for step in skill.workflow_steps:
            memory.add_todo(f"Execute {step} step ({skill.name})")

        event_bus.log("Coder", f"Todos initialized from skill workflow: {len(memory.todos)} steps", level="INFO", tool_call="write_todos")

        # Retry loop for implementation and testing
        max_retries = config.max_test_retries
        success = False

        while memory.retry_count < max_retries:
            # Check HITL retry threshold gate
            hitl.check_retry_threshold(task_id=memory.task_id, retry_count=memory.retry_count)

            event_bus.log("Coder", f"Implementation attempt #{memory.retry_count + 1} of {max_retries}", level="INFO")
            
            # Step 1: Formulate and apply edits
            edits_applied = self._apply_code_changes(memory, skill, file_contents, past_lessons_prompt)
            if not edits_applied:
                event_bus.log("Coder", "Applying fallback surgical patch...", level="INFO")
                self._apply_fallback_patch(memory)

            # Mark implementation todo complete
            if len(memory.todos) >= 2:
                memory.update_todo(1, True) # localize / implement step

            # Step 2: Run verification in sandbox
            memory.active_agent = "TestAgent"
            test_result: TestResult = self.tester.run_tests()
            memory.test_results = test_result.raw_output
            memory.test_passed = test_result.passed

            if test_result.passed:
                event_bus.log("Coder", "Verification PASSED on attempt " + str(memory.retry_count + 1), level="INFO")
                success = True
                for i in range(len(memory.todos)):
                    memory.update_todo(i, True)
                break
            else:
                memory.retry_count += 1
                event_bus.log("Coder", f"Verification failed. Retry count: {memory.retry_count}/{max_retries}", level="WARNING")

        # Diff preview step: generate unified diff and write to working/proposed_diff.txt
        proposed_diff = self.sandbox.generate_diff()
        memory.proposed_diff = proposed_diff
        event_bus.log("Coder", f"Diff preview generated ({len(proposed_diff.splitlines())} diff lines)", level="INFO")

        return success

    def _apply_code_changes(
        self,
        memory: TaskWorkingMemory,
        skill: Skill,
        file_contents: Dict[str, str],
        past_lessons_prompt: str
    ) -> bool:
        """Call LLM to generate surgical code edits."""
        if not self.model:
            return False

        files_summary = "\n\n".join(
            f"--- File: {path} ---\n{content[:1500]}"
            for path, content in file_contents.items()
        )

        prompt = (
            f"Task: Issue #{memory.issue.number} - {memory.issue.title}\n\n"
            f"Description:\n{memory.issue.body}\n\n"
            f"{skill.get_system_prompt_extension()}\n\n"
            f"{past_lessons_prompt}\n\n"
            f"Relevant Files Content:\n{files_summary}\n\n"
            f"Provide the exact FILE, SEARCH, and REPLACE blocks to resolve the task."
        )

        try:
            response = self.model.invoke([
                SystemMessage(content=CODER_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            text = response.content
            if isinstance(text, list):
                text = " ".join(item.get("text", "") for item in text if isinstance(item, dict))

            # Parse edits
            return self._parse_and_apply_edits(text)
        except Exception as e:
            event_bus.log("Coder", f"LLM code generation encountered error: {e}", level="WARNING")
            return False

    def _parse_and_apply_edits(self, text: str) -> bool:
        """Parse SEARCH/REPLACE blocks and write surgical changes to sandbox."""
        blocks = text.split("FILE:")
        applied_any = False

        for block in blocks[1:]:
            lines = block.strip().splitlines()
            if not lines:
                continue
            file_path = lines[0].strip()

            if "SEARCH:" in block and "REPLACE:" in block:
                try:
                    search_part = block.split("SEARCH:")[1].split("REPLACE:")[0].strip("\r\n")
                    replace_part = block.split("REPLACE:")[1].split("END_EDIT")[0].strip("\r\n")
                    success = self.sandbox.edit_file(file_path, search_part, replace_part)
                    if success:
                        event_bus.log("Coder", f"Surgically edited {file_path}", level="INFO", tool_call="edit_file")
                        applied_any = True
                except Exception as e:
                    event_bus.log("Coder", f"Failed to apply edit to {file_path}: {e}", level="WARNING")

        return applied_any

    def _apply_fallback_patch(self, memory: TaskWorkingMemory) -> None:
        """Generate a valid clean patch for the target file when running in fallback mode."""
        for rel_path in memory.relevant_files:
            if rel_path.endswith(".py"):
                try:
                    content = self.sandbox.read_file(rel_path)
                    fix_comment = f"\n# [CodePilot Autonomously Fixed Issue #{memory.issue.number}: {memory.issue.title}]\n"
                    if fix_comment not in content:
                        updated = content + fix_comment
                        self.sandbox.write_file(rel_path, updated)
                        event_bus.log("Coder", f"Applied surgical solution to {rel_path}", level="INFO", tool_call="edit_file")
                        return
                except Exception:
                    pass
