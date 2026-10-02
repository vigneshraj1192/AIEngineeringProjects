"""Structured models for CodePilot skills."""

from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from codepilot.state import TaskType

class Skill(BaseModel):
    """Structured Skill object for reusable agent capabilities."""
    name: str
    task_type: TaskType
    instructions: str
    workflow_steps: List[str] = Field(default_factory=list)
    example_prompts: List[str] = Field(default_factory=list)
    forbidden_actions: List[str] = Field(default_factory=list)
    checklist: List[str] = Field(default_factory=list)
    skill_dir: Optional[Path] = None

    def get_system_prompt_extension(self) -> str:
        """Format skill into concise prompt instructions for subagents."""
        steps_str = "\n".join(f"{idx+1}. {step}" for idx, step in enumerate(self.workflow_steps))
        checklist_str = "\n".join(f"- [ ] {item}" for item in self.checklist)
        forbidden_str = "\n".join(f"- {action}" for action in self.forbidden_actions)
        
        return (
            f"=== LOADED SKILL: {self.name} ===\n\n"
            f"Purpose & Instructions:\n{self.instructions}\n\n"
            f"Mandatory Workflow Steps:\n{steps_str}\n\n"
            f"Checklist Requirements:\n{checklist_str}\n\n"
            f"Forbidden Actions:\n{forbidden_str}\n"
        )
