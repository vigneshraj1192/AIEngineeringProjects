"""Unit tests for CodePilot specialist subagents: Sandbox, Tester, and PR Agent."""

import pytest
from pathlib import Path
from codepilot.state import TaskWorkingMemory, TaskType, IssueItem, TaskStatus
from codepilot.sandbox.local_sandbox import LocalSandbox
from codepilot.agents.tester import TestAgent
from codepilot.agents.pr_agent import PRAgent
from codepilot.github.client import github_client
from codepilot.guardrails.hitl import hitl

SAMPLE_REPO_DIR = Path(__file__).resolve().parent.parent / "sample_repo"

def test_sandbox_isolated_file_operations(tmp_path):
    hitl.set_auto_approve(True)
    sandbox = LocalSandbox(
        task_id="test_agent_task_1",
        source_repo=SAMPLE_REPO_DIR,
        relevant_files=["src/auth/oauth.py"]
    )

    # Read original
    content = sandbox.read_file("src/auth/oauth.py")
    assert "class OAuthHandler" in content

    # Edit file
    success = sandbox.edit_file(
        "src/auth/oauth.py",
        "client_id: str = \"devstream_client\"",
        "client_id: str = \"modified_client\""
    )
    assert success
    assert "modified_client" in sandbox.read_file("src/auth/oauth.py")

    # Generate diff preview
    diff = sandbox.generate_diff()
    assert "--- a/src/auth/oauth.py" in diff
    assert "+        self.client_id = client_id" in diff or "-        self.client_id" in diff or "modified_client" in diff
    assert (sandbox.working_dir / "proposed_diff.txt").exists()

def test_pr_agent_branch_naming_and_commit():
    hitl.set_auto_approve(True)
    pr_agent = PRAgent(client=github_client)

    issue = IssueItem(
        number=42,
        title="Fix null pointer exception in user auth redirect handler",
        body="OAuth callback fails with AttributeError",
        labels=["bug", "auth"],
        author="alice"
    )
    memory = TaskWorkingMemory(
        task_id="t42",
        issue=issue,
        task_type=TaskType.BUG_FIX,
        status=TaskStatus.TESTING,
        relevant_files=["src/auth/oauth.py"],
        proposed_diff="diff --git a/oauth.py b/oauth.py",
        test_results="1 passed in 0.05s"
    )

    pr = pr_agent.create_pr_for_task(memory)
    assert memory.branch_name.startswith("codepilot/issue-42-")
    assert "fix-null-pointer" in memory.branch_name
    assert pr["number"] > 0
    assert "[CodePilot] Fix null pointer" in pr["title"]
    assert "Closes #42" in pr["body"]
    assert "codepilot-generated" in pr["labels"]
