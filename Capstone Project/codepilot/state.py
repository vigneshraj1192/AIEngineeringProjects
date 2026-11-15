"""State machine and data models for CodePilot tasks and agents."""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import time

class TaskStatus(str, Enum):
    """Orchestrator state machine per task."""
    PENDING = "PENDING"
    TRIAGED = "TRIAGED"
    EXPLORING = "EXPLORING"
    IMPLEMENTING = "IMPLEMENTING"
    TESTING = "TESTING"
    PR_OPENED = "PR_OPENED"
    DONE = "DONE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

class TaskType(str, Enum):
    """Task classification categories."""
    BUG_FIX = "bug_fix"
    FEATURE_ADDITION = "feature_addition"
    DEPENDENCY_UPDATE = "dependency_update"
    DOCUMENTATION = "documentation"
    CONFIG_CHANGE = "config_change"

class IssueItem(BaseModel):
    """GitHub Issue representation."""
    number: int
    title: str
    body: str
    labels: List[str] = Field(default_factory=list)
    state: str = "open"
    author: str = "engineer"
    assignee: Optional[str] = None
    complexity_score: Optional[int] = None
    url: Optional[str] = None

class TodoItem(BaseModel):
    """Checklist item managed by write_todos."""
    id: str
    description: str
    completed: bool = False

class HITLApprovalRequest(BaseModel):
    """Human-in-the-loop approval request surfaced in TUI."""
    id: str
    task_id: str
    operation: str
    reason: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    status: str = "pending" # pending, approved, rejected

class TaskWorkingMemory(BaseModel):
    """Working Memory (task-scoped, in-memory)."""
    task_id: str
    issue: IssueItem
    task_type: TaskType
    status: TaskStatus = TaskStatus.TRIAGED
    active_agent: str = "Orchestrator"
    skill_name: Optional[str] = None
    todos: List[TodoItem] = Field(default_factory=list)
    relevant_files: List[str] = Field(default_factory=list)
    proposed_diff: Optional[str] = None
    test_results: Optional[str] = None
    test_passed: bool = False
    retry_count: int = 0
    branch_name: Optional[str] = None
    commit_sha: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    error_message: Optional[str] = None
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    sandbox_path: Optional[str] = None

    def add_todo(self, description: str, completed: bool = False) -> None:
        todo_id = f"todo_{len(self.todos) + 1}"
        self.todos.append(TodoItem(id=todo_id, description=description, completed=completed))

    def update_todo(self, index: int, completed: bool) -> None:
        if 0 <= index < len(self.todos):
            self.todos[index].completed = completed
