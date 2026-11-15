"""Unit tests for CodePilot's 3-tier memory system: Working, Episodic, Semantic."""

import pytest
import time
from pathlib import Path
from codepilot.state import IssueItem, TaskType, TaskStatus, TaskWorkingMemory
from codepilot.memory.working import working_memory
from codepilot.memory.episodic import episodic_memory
from codepilot.memory.semantic import semantic_memory

def test_working_memory_lifecycle():
    issue = IssueItem(number=10, title="Test Issue", body="Description", labels=["bug"])
    memory = working_memory.initialize_task(issue=issue, task_type=TaskType.BUG_FIX)
    
    assert memory.status == TaskStatus.TRIAGED
    assert memory.active_agent == "Orchestrator"

    memory.add_todo("Step 1: Reproduce")
    memory.add_todo("Step 2: Fix")
    assert len(memory.todos) == 2
    assert not memory.todos[0].completed

    memory.update_todo(0, True)
    assert memory.todos[0].completed

    working_memory.update_status(TaskStatus.IMPLEMENTING, agent_name="Coder")
    assert memory.status == TaskStatus.IMPLEMENTING
    assert memory.active_agent == "Coder"

    working_memory.clear()
    assert working_memory.current is None

def test_episodic_memory_session_tracking(tmp_path):
    issue = IssueItem(number=99, title="Episodic Test Issue", body="Body")
    memory = TaskWorkingMemory(
        task_id="t99",
        issue=issue,
        task_type=TaskType.BUG_FIX,
        status=TaskStatus.DONE,
        relevant_files=["src/test.py"],
        start_time=time.time() - 5,
        end_time=time.time(),
    )

    record = episodic_memory.record_task_outcome(memory)
    assert record.issue_number == 99
    assert record.outcome == TaskStatus.DONE.value

    summary = episodic_memory.save_session_summary()
    assert summary.total_tasks >= 1
    assert summary.successful_tasks >= 1

    recent_summaries = episodic_memory.get_recent_session_summaries(limit=3)
    assert len(recent_summaries) >= 1

def test_semantic_memory_chroma_lessons():
    lesson = semantic_memory.record_lesson(
        repository="devstream-labs/sample-repo",
        issue_number=142,
        issue_title="OAuth query param encoding issue",
        task_type="bug_fix",
        files_modified=["src/auth/oauth.py"],
        approach="Use urllib.parse.quote on redirect_uri query string."
    )
    assert lesson.id is not None
    assert lesson.issue_number == 142

    # Query ChromaDB
    retrieved = semantic_memory.retrieve_relevant_lessons(
        repository="devstream-labs/sample-repo",
        query="OAuth redirect_uri query parameter issue",
        task_type="bug_fix",
        top_k=3
    )
    assert len(retrieved) > 0
    prompt_str = semantic_memory.format_lessons_for_prompt(retrieved)
    assert "PRIOR LESSONS LEARNED" in prompt_str
