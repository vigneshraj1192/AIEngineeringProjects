"""GitHub integration package for CodePilot."""

from codepilot.github.client import github_client, GitHubClient
from codepilot.github.toolkit import get_github_tools, list_open_issues, get_issue_details

__all__ = [
    "github_client",
    "GitHubClient",
    "get_github_tools",
    "list_open_issues",
    "get_issue_details",
]
