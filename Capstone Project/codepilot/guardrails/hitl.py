"""Human-in-the-loop (HITL) gates and approval controller."""

import uuid
import threading
from typing import Dict, Any, Optional, Callable
from codepilot.state import HITLApprovalRequest
from codepilot.tui.event_bus import event_bus, EventType
from codepilot.config import config

class HITLRejectedException(Exception):
    """Raised when a human rejects an HITL request."""
    def __init__(self, operation: str, reason: str):
        super().__init__(f"Operation '{operation}' was rejected by human operator: {reason}")
        self.operation = operation
        self.reason = reason

class HITLController:
    """Manages pause/resume gates requiring explicit human approval."""

    def __init__(self):
        self._pending_requests: Dict[str, HITLApprovalRequest] = {}
        self._events: Dict[str, threading.Event] = {}
        self._decisions: Dict[str, str] = {} # "approve", "reject"
        self._auto_approve: bool = False
        self._approval_handler: Optional[Callable[[HITLApprovalRequest], str]] = None

    def set_auto_approve(self, auto: bool) -> None:
        """Enable auto-approval for non-interactive test suites."""
        self._auto_approve = auto

    def set_approval_handler(self, handler: Callable[[HITLApprovalRequest], str]) -> None:
        """Set custom callback for approval decisions (used by CLI or TUI)."""
        self._approval_handler = handler

    def request_approval(
        self,
        task_id: str,
        operation: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Request human approval for a protected operation.
        Blocks until approved or rejected.
        Returns True if approved, raises HITLRejectedException if rejected.
        """
        if self._auto_approve:
            event_bus.log("HITL", f"Auto-approving gate: {operation} ({reason})", level="INFO")
            return True

        req_id = str(uuid.uuid4())[:8]
        request = HITLApprovalRequest(
            id=req_id,
            task_id=task_id,
            operation=operation,
            reason=reason,
            details=details or {},
            status="pending"
        )

        # If a custom synchronous handler is attached (e.g. CLI interactive prompt)
        if self._approval_handler:
            decision = self._approval_handler(request)
            if decision == "approve":
                event_bus.log("HITL", f"Human APPROVED: {operation}", level="INFO")
                return True
            else:
                event_bus.log("HITL", f"Human REJECTED: {operation}", level="WARNING")
                raise HITLRejectedException(operation, reason)

        # Textual TUI / asynchronous event waiting
        self._pending_requests[req_id] = request
        event = threading.Event()
        self._events[req_id] = event

        event_bus.emit(EventType.HITL_PROMPT, request.model_dump())
        event_bus.log("HITL", f"Paused for human approval: {operation} — Reason: {reason}", level="WARNING")

        # Wait for user input from TUI
        event.wait()

        decision = self._decisions.get(req_id, "reject")
        del self._pending_requests[req_id]
        del self._events[req_id]
        if req_id in self._decisions:
            del self._decisions[req_id]

        if decision == "approve":
            event_bus.emit(EventType.HITL_RESOLVED, {"id": req_id, "status": "approved"})
            event_bus.log("HITL", f"Human APPROVED: {operation}", level="INFO")
            return True
        else:
            event_bus.emit(EventType.HITL_RESOLVED, {"id": req_id, "status": "rejected"})
            event_bus.log("HITL", f"Human REJECTED: {operation}", level="WARNING")
            raise HITLRejectedException(operation, reason)

    def resolve(self, request_id: str, decision: str) -> None:
        """Called by TUI when user clicks Approve or Reject."""
        if request_id in self._events:
            self._decisions[request_id] = decision
            self._events[request_id].set()

    # Convenience Gate Checks
    def check_pr_target_branch(self, task_id: str, branch: str) -> None:
        """HITL Gate: Opening PR to main or master."""
        if branch.lower() in ("main", "master"):
            self.request_approval(
                task_id=task_id,
                operation=f"Open PR to {branch}",
                reason="Target branch is default production branch (main/master). Irreversible without revert.",
                details={"target_branch": branch}
            )

    def check_commit_file_count(self, task_id: str, file_count: int, file_list: list[str]) -> None:
        """HITL Gate: Committing more than 5 files."""
        if file_count > config.max_commit_files:
            self.request_approval(
                task_id=task_id,
                operation=f"Commit {file_count} files",
                reason=f"Commit touches {file_count} files (threshold is {config.max_commit_files}). Risk of unintended scope.",
                details={"file_count": file_count, "files": file_list}
            )

    def check_command_execution(self, task_id: str, command: str) -> None:
        """HITL Gate: Any execute call containing git push or network commands."""
        if "git push" in command.lower():
            self.request_approval(
                task_id=task_id,
                operation=f"Execute: {command}",
                reason="Command contains 'git push' (network operation modifying remote repository).",
                details={"command": command}
            )

    def check_retry_threshold(self, task_id: str, retry_count: int) -> None:
        """HITL Gate: Retry after 2 failed test runs."""
        if retry_count >= config.hitl_retry_threshold:
            self.request_approval(
                task_id=task_id,
                operation=f"Retry {retry_count + 1} after {retry_count} test failures",
                reason=f"Task has failed tests {retry_count} times. Requires approval to prevent infinite loop.",
                details={"retry_count": retry_count}
            )

hitl = HITLController()
