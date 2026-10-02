"""Skills loader and registry for CodePilot."""

from pathlib import Path
from typing import Dict, List, Optional
from codepilot.state import TaskType
from codepilot.skills.models import Skill

SKILLS_DIR = Path(__file__).resolve().parent

class SkillsRegistry:
    """Registry that manages structured skills and maps them to task types."""
    
    def __init__(self, root_dir: Path = SKILLS_DIR):
        self.root_dir = root_dir
        self._skills: Dict[str, Skill] = {}
        self._init_skills()

    def _init_skills(self) -> None:
        """Register the built-in skills with structured definitions."""
        self._skills["bug_fix_skill"] = Skill(
            name="bug_fix_skill",
            task_type=TaskType.BUG_FIX,
            instructions="Reproduce the bug first with a failing test, localize the root cause in the codebase, apply a surgical fix, and verify resolution.",
            workflow_steps=["reproduce", "localize", "fix", "verify"],
            example_prompts=[
                "Fix the NullPointer exception in user profile auth handler.",
                "Resolve ValueError when parsing empty JSON payloads in webhook endpoint."
            ],
            forbidden_actions=[
                "Do not mark task complete without a passing test in sandbox.",
                "Do not perform broad refactorings outside the bug scope.",
                "Do not swallow errors with bare except clauses."
            ],
            checklist=[
                "Reproduce failure before writing production code",
                "Check for None/null pointer dereferences or missing keys",
                "Validate type boundaries, off-by-one errors, and edge case arguments",
                "Ensure backward compatibility with existing callers",
                "Verify clean exit without leftover temp state"
            ],
            skill_dir=self.root_dir / "bug_fix_skill",
        )

        self._skills["feature_addition_skill"] = Skill(
            name="feature_addition_skill",
            task_type=TaskType.FEATURE_ADDITION,
            instructions="Understand existing codebase patterns, design clean interfaces, implement feature incrementally, test thoroughly, and document.",
            workflow_steps=["explore_pattern", "design", "implement", "test", "document"],
            example_prompts=[
                "Add an export to CSV endpoint to the analytics service.",
                "Support webhook retry backoff configuration in worker queue."
            ],
            forbidden_actions=[
                "Do not introduce breaking changes to existing public APIs unless asked.",
                "Do not add undocumented dependencies.",
                "Do not rewrite existing working subsystems."
            ],
            checklist=[
                "Match existing naming conventions (snake_case vs camelCase)",
                "Validate all new inputs and provide clear error messages",
                "Maintain full backward compatibility for existing callers",
                "Include clear docstrings with argument and return specifications",
                "Verify test suite passes without regressions"
            ],
            skill_dir=self.root_dir / "feature_addition_skill",
        )

        self._skills["dependency_update_skill"] = Skill(
            name="dependency_update_skill",
            task_type=TaskType.DEPENDENCY_UPDATE,
            instructions="Inspect upstream changelog, update package version specs, resolve breaking changes or API shifts, and run full test suite.",
            workflow_steps=["check_changelog", "update", "resolve_conflicts", "test_all"],
            example_prompts=[
                "Upgrade pydantic from v1 to v2 across data pipeline models.",
                "Bump cryptography library to resolve vulnerability CVE-2026-1123."
            ],
            forbidden_actions=[
                "Do not blindly bump major versions without inspecting changelogs.",
                "Do not delete failing tests to fake compatibility.",
                "Do not bypass lockfile or hash validations."
            ],
            checklist=[
                "Check breaking change notes in package release changelogs",
                "Update requirements or pyproject files accurately",
                "Fix deprecated imports or keyword arguments",
                "Run test suite to verify end-to-end functionality"
            ],
            skill_dir=self.root_dir / "dependency_update_skill",
        )

        self._skills["documentation_skill"] = Skill(
            name="documentation_skill",
            task_type=TaskType.DOCUMENTATION,
            instructions="Match existing documentation voice and style, write concise technical explanations, add runnable code examples, and update references.",
            workflow_steps=["read_existing", "draft", "review_accuracy", "update_index"],
            example_prompts=[
                "Add tutorial guide and examples for the custom plugin system.",
                "Update README.md with newly added CLI flags and environment variables."
            ],
            forbidden_actions=[
                "Do not add hypothetical or unverified features to documentation.",
                "Do not leave placeholder text or broken links.",
                "Do not modify production code logic when only documentation was requested."
            ],
            checklist=[
                "Match existing Markdown formatting style",
                "Ensure all code snippets in examples are syntactically valid",
                "Update README / user guide if public CLI or API behavior changes",
                "Verify relative links and table of contents resolve cleanly"
            ],
            skill_dir=self.root_dir / "documentation_skill",
        )

    def load(self, name_or_type: str | TaskType) -> Skill:
        """Load a skill by name or TaskType."""
        if isinstance(name_or_type, TaskType):
            name_or_type = name_or_type.value

        # Match direct skill name
        if name_or_type in self._skills:
            return self._skills[name_or_type]

        # Match task type string
        for skill in self._skills.values():
            if skill.task_type.value == name_or_type:
                return skill

        # Fallback to bug_fix_skill
        return self._skills["bug_fix_skill"]

    def list_skills(self) -> Dict[str, Skill]:
        return self._skills

    def get_skill_paths(self) -> List[str]:
        """Return list of skill directory paths for DeepAgents skills middleware."""
        paths = []
        for skill in self._skills.values():
            if skill.skill_dir and skill.skill_dir.exists():
                paths.append(str(skill.skill_dir.resolve()))
        return paths

skills = SkillsRegistry()
