"""Working memory management for task-scoped state."""

from typing import Optional, Dict
from codepilot.state import TaskWorkingMemory, IssueItem, TaskType, TaskStatus

class WorkingMemoryManager:
    """Manages task-scoped in-memory state."""
    
    def __init__(self):
        self._active_task: Optional[TaskWorkingMemory] = None

    def initialize_task(self, issue: IssueItem, task_type: TaskType, sandbox_path: Optional[str] = None) -> TaskWorkingMemory:
        """Create and activate working memory for a new task."""
        task_id = f"task_{issue.number}_{int(time.time())}"
        self._active_task = TaskWorkingMemory(
            task_id=task_id,
            issue=issue,
            task_type=task_type,
            status=TaskStatus.TRIAGED,
            active_agent="Orchestrator",
            sandbox_path=sandbox_path,
        )
        return self._active_task

    @property
    def current(self) -> Optional[TaskWorkingMemory]:
        """Get currently active task working memory."""
        return self._active_task

    def update_status(self, status: TaskStatus, agent_name: Optional[str] = None) -> None:
        """Update the active task status and agent."""
        if self._active_task:
            self._active_task.status = status
            if agent_name:
                self._active_task.active_agent = agent_name

    def clear(self) -> None:
        """Clear working memory when task finishes."""
        self._active_task = None

import time

working_memory = WorkingMemoryManager()
