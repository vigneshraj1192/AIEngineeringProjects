"""Skills system for CodePilot."""

from codepilot.skills.models import Skill
from codepilot.skills.loader import skills, SkillsRegistry

__all__ = ["Skill", "skills", "SkillsRegistry"]
