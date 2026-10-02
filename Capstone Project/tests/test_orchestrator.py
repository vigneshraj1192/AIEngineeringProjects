"""Unit tests for the Orchestrator Agent lifecycle and state machine."""

import pytest
from pathlib import Path
from codepilot.agents.orchestrator import OrchestratorAgent
from codepilot.state import IssueItem, TaskType, TaskStatus
from codepilot.guardrails.hitl import hitl

SAMPLE_REPO_DIR = Path(__file__).resolve().parent.parent / "sample_repo"

def test_task_classification():
    orchestrator = OrchestratorAgent(repo_path=SAMPLE_REPO_DIR)

    bug_issue = IssueItem(number=1, title="Fix crash in auth", body="Null pointer", labels=["bug"])
    feat_issue = IssueItem(number=2, title="Add CSV export endpoint", body="New feature", labels=["feature"])
    dep_issue = IssueItem(number=3, title="Upgrade pydantic to v2", body="Bump dependency", labels=["dependencies"])
    doc_issue = IssueItem(number=4, title="Update README docs", body="Documentation fix", labels=["documentation"])

    assert orchestrator.classify_task(bug_issue) == TaskType.BUG_FIX
    assert orchestrator.classify_task(feat_issue) == TaskType.FEATURE_ADDITION
    assert orchestrator.classify_task(dep_issue) == TaskType.DEPENDENCY_UPDATE
    assert orchestrator.classify_task(doc_issue) == TaskType.DOCUMENTATION

def test_complexity_scoring_and_skipping():
    orchestrator = OrchestratorAgent(repo_path=SAMPLE_REPO_DIR)

    normal_issue = IssueItem(number=42, title="Fix typo in docs", body="Simple typo", complexity_score=2)
    assert orchestrator.score_complexity(normal_issue) == 2

    heavy_issue = IssueItem(
        number=59,
        title="Rewrite distributed database architecture from scratch",
        body="High complexity overhaul",
        complexity_score=10
    )
    assert orchestrator.score_complexity(heavy_issue) == 10

    # Process heavy issue should skip
    status = orchestrator.process_issue(heavy_issue)
    assert status == TaskStatus.SKIPPED

def test_full_autonomous_pipeline_execution():
    hitl.set_auto_approve(True)
    orchestrator = OrchestratorAgent(repo_path=SAMPLE_REPO_DIR)

    issue = IssueItem(
        number=45,
        title="Add CSV export functionality to metrics report API",
        body="Implement GET /api/v1/metrics/export?format=csv adhering to existing report formats",
        labels=["ai-assignable", "feature"],
        author="alice",
        complexity_score=4
    )

    status = orchestrator.process_issue(issue)
    assert status == TaskStatus.DONE
