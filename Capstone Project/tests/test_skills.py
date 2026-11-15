"""Unit tests for the CodePilot Skills system."""

import pytest
from codepilot.skills.loader import skills
from codepilot.state import TaskType

def test_four_skills_loaded():
    all_skills = skills.list_skills()
    assert "bug_fix_skill" in all_skills
    assert "feature_addition_skill" in all_skills
    assert "dependency_update_skill" in all_skills
    assert "documentation_skill" in all_skills

def test_skill_structure():
    bug_skill = skills.load("bug_fix_skill")
    assert bug_skill.name == "bug_fix_skill"
    assert bug_skill.task_type == TaskType.BUG_FIX
    assert bug_skill.workflow_steps == ["reproduce", "localize", "fix", "verify"]
    assert len(bug_skill.checklist) > 0
    assert len(bug_skill.forbidden_actions) > 0

    feat_skill = skills.load("feature_addition_skill")
    assert feat_skill.workflow_steps == ["explore_pattern", "design", "implement", "test", "document"]

    dep_skill = skills.load("dependency_update_skill")
    assert dep_skill.workflow_steps == ["check_changelog", "update", "resolve_conflicts", "test_all"]

    doc_skill = skills.load("documentation_skill")
    assert doc_skill.workflow_steps == ["read_existing", "draft", "review_accuracy", "update_index"]

def test_load_by_task_type():
    assert skills.load(TaskType.BUG_FIX).name == "bug_fix_skill"
    assert skills.load(TaskType.FEATURE_ADDITION).name == "feature_addition_skill"
    assert skills.load(TaskType.DEPENDENCY_UPDATE).name == "dependency_update_skill"
    assert skills.load(TaskType.DOCUMENTATION).name == "documentation_skill"

def test_skill_prompt_extension():
    bug_skill = skills.load("bug_fix_skill")
    extension = bug_skill.get_system_prompt_extension()
    assert "=== LOADED SKILL: bug_fix_skill ===" in extension
    assert "reproduce" in extension
    assert "verify" in extension
