"""LangChain tool interfaces for GitHub integration."""

from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from codepilot.github.client import github_client
from codepilot.config import config

@tool
def list_open_issues(filter_label: str = "ai-assignable") -> str:
    """List open, unassigned GitHub issues matching the AI filter label."""
    issues = github_client.list_issues(state="open", filter_label=filter_label)
    if not issues:
        return "No open issues found matching filter."
    
    lines = []
    for issue in issues:
        lines.append(f"#{issue.number} [{issue.title}] (labels: {', '.join(issue.labels)}) - Author: {issue.author}")
    return "\n".join(lines)

@tool
def get_issue_details(issue_number: int) -> str:
    """Get full description, author, labels, and state for a specific issue number."""
    issue = github_client.get_issue(issue_number)
    if not issue:
        return f"Issue #{issue_number} not found."
    return (
        f"Issue #{issue.number}: {issue.title}\n"
        f"Author: {issue.author}\n"
        f"Labels: {', '.join(issue.labels)}\n"
        f"State: {issue.state}\n\n"
        f"Description:\n{issue.body}"
    )

@tool
def create_github_branch(branch_name: str) -> str:
    """Create a new working branch in the repository."""
    success = github_client.create_branch(branch_name)
    if success:
        return f"Successfully created branch '{branch_name}'."
    return f"Failed to create branch '{branch_name}'."

@tool
def create_pull_request(
    title: str,
    body: str,
    head_branch: str,
    base_branch: str = "main",
) -> str:
    """Open a GitHub pull request with structured body and labels."""
    pr = github_client.create_pull_request(
        title=title,
        body=body,
        head_branch=head_branch,
        base_branch=base_branch,
        labels=["codepilot-generated", "needs-review"],
    )
    return f"Pull Request #{pr['number']} opened successfully: {pr['url']}"

def get_github_tools():
    """Return list of LangChain tools for Orchestrator and PR Agent."""
    return [list_open_issues, get_issue_details, create_github_branch, create_pull_request]
