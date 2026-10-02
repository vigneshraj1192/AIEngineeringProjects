"""Episodic memory management for session-scoped execution records."""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from codepilot.config import config
from codepilot.state import TaskWorkingMemory, TaskStatus

class TaskAttemptRecord(BaseModel):
    """Execution record for an individual task attempted during a session."""
    task_id: str
    issue_number: int
    issue_title: str
    task_type: str
    files_modified: List[str] = Field(default_factory=list)
    outcome: str
    duration_seconds: float
    error_message: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)

class SessionSummary(BaseModel):
    """Structured summary of a completed CodePilot session."""
    session_id: str
    start_time: float
    end_time: float
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    records: List[TaskAttemptRecord] = Field(default_factory=list)
    failed_issue_numbers: List[int] = Field(default_factory=list)

class EpisodicMemoryStore:
    """Session-scoped memory store preserving execution history and preventing duplicate failures."""
    
    def __init__(self, store_dir: Path = config.memory_store_dir):
        self.store_dir = store_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.current_session_id = f"session_{int(time.time())}"
        self.session_start_time = time.time()
        self.current_records: List[TaskAttemptRecord] = []

    def record_task_outcome(self, memory: TaskWorkingMemory) -> TaskAttemptRecord:
        """Record the outcome of a finished task in the current session."""
        duration = (memory.end_time or time.time()) - memory.start_time
        record = TaskAttemptRecord(
            task_id=memory.task_id,
            issue_number=memory.issue.number,
            issue_title=memory.issue.title,
            task_type=memory.task_type.value,
            files_modified=memory.relevant_files,
            outcome=memory.status.value,
            duration_seconds=round(duration, 2),
            error_message=memory.error_message,
        )
        self.current_records.append(record)
        return record

    def save_session_summary(self) -> SessionSummary:
        """Persist structured summary of current session to the memory store."""
        end_time = time.time()
        successful = sum(1 for r in self.current_records if r.outcome == TaskStatus.DONE.value)
        failed = sum(1 for r in self.current_records if r.outcome == TaskStatus.FAILED.value)
        failed_issues = [r.issue_number for r in self.current_records if r.outcome == TaskStatus.FAILED.value]

        summary = SessionSummary(
            session_id=self.current_session_id,
            start_time=self.session_start_time,
            end_time=end_time,
            total_tasks=len(self.current_records),
            successful_tasks=successful,
            failed_tasks=failed,
            records=self.current_records,
            failed_issue_numbers=failed_issues,
        )

        file_path = self.store_dir / f"{self.current_session_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(summary.model_dump_json(indent=2))

        return summary

    def get_recent_session_summaries(self, limit: int = 3) -> List[SessionSummary]:
        """Read the last N session summaries to extract historical context."""
        session_files = sorted(self.store_dir.glob("session_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        summaries = []
        for file in session_files[:limit]:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    summaries.append(SessionSummary(**data))
            except Exception:
                continue
        return summaries

    def get_recently_failed_issue_numbers(self, limit_sessions: int = 3) -> set[int]:
        """Return set of issue numbers that failed in the last N sessions."""
        failed = set()
        for summary in self.get_recent_session_summaries(limit=limit_sessions):
            failed.update(summary.failed_issue_numbers)
        # Also include any currently failed tasks in this active session
        for record in self.current_records:
            if record.outcome == TaskStatus.FAILED.value:
                failed.add(record.issue_number)
        return failed

episodic_memory = EpisodicMemoryStore()
