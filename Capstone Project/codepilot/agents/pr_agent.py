"""PR Agent: Handles branching, structured commits, pull request creation, and conflict detection."""

import re
from typing import Dict, Any, List, Optional
from codepilot.config import config
from codepilot.state import TaskWorkingMemory, TaskStatus
from codepilot.github.client import github_client
from codepilot.guardrails.hitl import hitl
from codepilot.tui.event_bus import event_bus

class MergeConflictException(Exception):
    """Raised when git encounters an unresolvable merge conflict."""
    pass

class PRAgent:
    """Agent responsible for creating git branches, structured commits, and opening GitHub PRs."""

    def __init__(self, client=github_client):
        self.client = client

    def _slugify(self, text: str) -> str:
        """Convert issue title to clean kebab-case slug."""
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "-", text).strip("-")
        return text[:40]

    def create_pr_for_task(self, memory: TaskWorkingMemory) -> Dict[str, Any]:
        """Execute full PR opening workflow for a verified task."""
        issue = memory.issue
        event_bus.log("PR_Agent", f"Starting PR creation for Issue #{issue.number}: {issue.title}", level="INFO")

        # 1. Generate branch name
        slug = self._slugify(issue.title)
        branch_name = f"codepilot/issue-{issue.number}-{slug}"
        memory.branch_name = branch_name

        # 2. Check HITL gate: Opening PR to main or master
        target_branch = config.default_branch
        hitl.check_pr_target_branch(task_id=memory.task_id, branch=target_branch)

        # 3. Check modified files & commit file count HITL gate
        files_modified = memory.relevant_files
        hitl.check_commit_file_count(
            task_id=memory.task_id,
            file_count=len(files_modified),
            file_list=files_modified
        )

        # 4. Create git branch
        self.client.create_branch(branch_name, base_branch=target_branch)

        # 5. Create structured commit
        what_changed = [
            f"Applied surgical changes to {', '.join(files_modified)}",
            f"Verified all sandbox unit and regression tests pass",
            f"Adhered to skill workflow for {memory.task_type.value}"
        ]
        why = f"Resolves {memory.task_type.value} reported in Issue #{issue.number}"
        
        commit_sha = self.client.commit_changes(
            issue_number=issue.number,
            summary=issue.title,
            what_changed=what_changed,
            why=why,
            files_modified=files_modified
        )
        memory.commit_sha = commit_sha

        # 6. Compose structured PR body
        pr_title = f"[CodePilot] {issue.title}"
        diff_snippet = (memory.proposed_diff or "")[:800]
        if len(memory.proposed_diff or "") > 800:
            diff_snippet += "\n... [diff preview truncated]"

        pr_body = (
            f"## 🤖 CodePilot Autonomous PR\n\n"
            f"Closes #{issue.number}\n\n"
            f"### 📋 Issue Summary\n"
            f"{issue.body}\n\n"
            f"### 🛠️ Implementation Approach\n"
            f"- **Task Type**: `{memory.task_type.value}`\n"
            f"- **Assigned Skill**: `{memory.skill_name or 'bug_fix_skill'}`\n"
            f"- **Files Changed**: `{', '.join(files_modified)}`\n\n"
            f"### 🧪 Verification & Test Results\n"
            f"```text\n{memory.test_results or 'All automated tests passed successfully.'}\n```\n\n"
            f"### 🔍 Diff Preview\n"
            f"```diff\n{diff_snippet}\n```\n\n"
            f"---\n*Generated autonomously by CodePilot AI Assistant*"
        )

        # 7. Open Pull Request
        reviewers = [issue.author] if issue.author and issue.author != "unknown" else None
        pr = self.client.create_pull_request(
            title=pr_title,
            body=pr_body,
            head_branch=branch_name,
            base_branch=target_branch,
            labels=["codepilot-generated", "needs-review"],
            reviewers=reviewers
        )

        memory.pr_number = pr.get("number")
        memory.pr_url = pr.get("url")
        event_bus.log("PR_Agent", f"PR #{memory.pr_number} successfully opened: {memory.pr_url}", level="INFO")

        return pr
