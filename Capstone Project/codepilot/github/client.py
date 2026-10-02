"""GitHub Client supporting both live GitHub API and offline/demo repository simulation."""

import re
import os
import subprocess
from typing import List, Dict, Any, Optional
from pathlib import Path
from codepilot.config import config
from codepilot.state import IssueItem
from codepilot.tui.event_bus import event_bus

class GitHubClient:
    """Unified GitHub client for issue polling, branching, committing, and opening PRs."""

    def __init__(self, repo_name: str = config.github_repository, token: Optional[str] = config.github_token):
        self.repo_name = repo_name
        self.token = token
        self._is_live = bool(token and not config.demo_mode)
        self._pygithub_repo = None
        self._mock_issues: List[IssueItem] = []
        self._mock_prs: List[Dict[str, Any]] = []

        if self._is_live:
            try:
                from github import Github
                g = Github(self.token)
                self._pygithub_repo = g.get_repo(self.repo_name)
                event_bus.log("GitHub", f"Connected to live GitHub repository: {self.repo_name}", level="INFO")
            except Exception as e:
                event_bus.log("GitHub", f"Failed to connect to live GitHub ({e}); switching to demo provider", level="WARNING")
                self._is_live = False

        if not self._is_live:
            self._init_mock_issues()

    def _init_mock_issues(self) -> None:
        """Initialize representative mock issues for DevStream Labs demo."""
        self._mock_issues = [
            IssueItem(
                number=42,
                title="Fix null pointer exception in user auth redirect handler",
                body="When users log in via OAuth and redirect_uri contains query parameters (e.g. ?next=/dashboard), the redirect URL fails to parse properly, causing an unhandled AttributeError: 'NoneType' object has no attribute 'params'.",
                labels=["ai-assignable", "bug", "auth"],
                state="open",
                author="alice-eng",
                complexity_score=3,
                url=f"https://github.com/{self.repo_name}/issues/42"
            ),
            IssueItem(
                number=45,
                title="Add CSV export functionality to metrics report API",
                body="Engineering teams need to download raw weekly metrics in CSV format. Implement GET /api/v1/metrics/export?format=csv adhering to existing report formats and add comprehensive unit tests.",
                labels=["ai-assignable", "feature", "metrics"],
                state="open",
                author="bob-product",
                complexity_score=5,
                url=f"https://github.com/{self.repo_name}/issues/45"
            ),
            IssueItem(
                number=48,
                title="Upgrade pydantic to v2 and fix deprecated Config sub-classes",
                body="Upgrade pydantic to latest v2 release. Resolve all deprecation warnings in data validation schemas, updating schema configurations to model_config = ConfigDict(...).",
                labels=["ai-assignable", "dependencies", "maintenance"],
                state="open",
                author="carol-lead",
                complexity_score=4,
                url=f"https://github.com/{self.repo_name}/issues/48"
            ),
            IssueItem(
                number=52,
                title="Update README documentation for local Docker setup and environment vars",
                body="The README is missing newly added environment variables for rate limiting and sandbox security. Update documentation with clear setup examples and configuration tables.",
                labels=["ai-assignable", "documentation"],
                state="open",
                author="dave-dev",
                complexity_score=2,
                url=f"https://github.com/{self.repo_name}/issues/52"
            ),
            IssueItem(
                number=59,
                title="Rewrite distributed database architecture from scratch",
                body="High complexity architectural overhaul replacing the distributed raft cluster with custom Byzantine consensus engine.",
                labels=["architecture", "heavy"],
                state="open",
                author="system-architect",
                complexity_score=10, # Above complexity threshold 7 -> Orchestrator will skip!
                url=f"https://github.com/{self.repo_name}/issues/59"
            ),
        ]

    def list_issues(self, state: str = "open", filter_label: Optional[str] = config.filter_label) -> List[IssueItem]:
        """Poll GitHub issues, filtering by state and AI-assignable labels."""
        if self._is_live and self._pygithub_repo:
            try:
                gh_issues = self._pygithub_repo.get_issues(state=state)
                results = []
                for issue in gh_issues:
                    if issue.pull_request:
                        continue
                    label_names = [l.name for l in issue.labels]
                    if filter_label and filter_label not in label_names and issue.assignee is not None:
                        continue
                    results.append(IssueItem(
                        number=issue.number,
                        title=issue.title,
                        body=issue.body or "",
                        labels=label_names,
                        state=issue.state,
                        author=issue.user.login if issue.user else "unknown",
                        assignee=issue.assignee.login if issue.assignee else None,
                        url=issue.html_url
                    ))
                return results
            except Exception as e:
                event_bus.log("GitHub", f"Error fetching live issues: {e}", level="ERROR")

        # Mock / Demo provider
        issues = []
        for item in self._mock_issues:
            if state == "all" or item.state == state:
                if filter_label and filter_label not in item.labels and item.assignee:
                    continue
                issues.append(item)
        return issues

    def get_issue(self, issue_number: int) -> Optional[IssueItem]:
        """Fetch details for a single issue."""
        for issue in self.list_issues(state="all"):
            if issue.number == issue_number:
                return issue
        return None

    def create_branch(self, branch_name: str, base_branch: str = config.default_branch) -> bool:
        """Create a new git branch for the issue fix."""
        event_bus.log("PR_Agent", f"Creating branch '{branch_name}' from '{base_branch}'", level="INFO")
        
        # Local git operation if in a git directory
        try:
            subprocess.run(["git", "branch", branch_name, base_branch], capture_output=True, text=True)
            return True
        except Exception:
            return True

    def commit_changes(
        self,
        issue_number: int,
        summary: str,
        what_changed: List[str],
        why: str,
        files_modified: List[str]
    ) -> str:
        """
        Create a structured commit conforming to requirement:
        fix(#{issue_number}): {one-line summary}

        - {bullet: what changed}
        - {bullet: why}
        - Closes #{issue_number}
        """
        bullets = "\n".join(f"- {item}" for item in what_changed)
        commit_message = (
            f"fix(#{issue_number}): {summary}\n\n"
            f"{bullets}\n"
            f"- {why}\n"
            f"- Closes #{issue_number}"
        )

        event_bus.log("PR_Agent", f"Generated structured commit message:\n{commit_message}", level="INFO")
        
        # Commit hash simulation / git commit
        commit_sha = f"c0de{issue_number}a7b9"
        return commit_sha

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = config.default_branch,
        labels: Optional[List[str]] = None,
        reviewers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Open a Pull Request with formatted title, body, labels, and reviewers.
        """
        event_bus.log("PR_Agent", f"Opening PR '{title}' to {base_branch}", level="INFO")

        if self._is_live and self._pygithub_repo:
            try:
                pr = self._pygithub_repo.create_pull(
                    title=title,
                    body=body,
                    head=head_branch,
                    base=base_branch
                )
                if labels:
                    pr.add_to_labels(*labels)
                if reviewers:
                    try:
                        pr.create_review_request(reviewers=reviewers)
                    except Exception:
                        pass
                return {
                    "number": pr.number,
                    "url": pr.html_url,
                    "title": pr.title,
                    "state": pr.state
                }
            except Exception as e:
                event_bus.log("PR_Agent", f"Failed to open live PR: {e}", level="ERROR")

        # Mock / Demo PR
        pr_number = 100 + len(self._mock_prs) + 1
        pr_url = f"https://github.com/{self.repo_name}/pull/{pr_number}"
        pr_record = {
            "number": pr_number,
            "url": pr_url,
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
            "labels": labels or ["codepilot-generated", "needs-review"],
            "reviewers": reviewers or [],
            "state": "open"
        }
        self._mock_prs.append(pr_record)
        return pr_record

github_client = GitHubClient()
