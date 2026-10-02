"""Repo Explorer Agent: Maps codebase, extracts context, and retrieves relevant files."""

from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from codepilot.config import config
from codepilot.context.repo_map import RepoMapBuilder, RepoMap
from codepilot.context.retrieval import CodeRetriever
from codepilot.tui.event_bus import event_bus

REPO_EXPLORER_PROMPT = """
You are the Repo Explorer agent for CodePilot.
Your responsibility:
- Analyze the codebase without reading every file.
- Understand project structure, module boundaries, and exported symbols from the Repo Map.
- Select the most relevant files needed to diagnose and fix the given task.
- Follow strict context engineering principles: return file paths only, never dump raw file contents.
"""

class RepoExplorerAgent:
    """Agent responsible for codebase analysis, map generation, and file retrieval."""

    def __init__(self, repo_path: Path, model: Optional[BaseChatModel] = None):
        self.repo_path = Path(repo_path).resolve()
        self.model = model
        self.map_builder = RepoMapBuilder(self.repo_path)
        self.retriever = CodeRetriever(self.repo_path)

    def explore(self, task_description: str, top_k: int = 10, strategy: Optional[str] = None) -> Dict[str, Any]:
        """
        Builds/loads Repo Map and retrieves top-K relevant files for task.
        Returns dict containing repo_map, relevant_files, and formatted context.
        """
        event_bus.log("RepoExplorer", f"Exploring codebase for task: '{task_description[:60]}...'", level="INFO")
        
        # 1. Build or retrieve cached Repo Map within token budget
        repo_map = self.map_builder.build_or_load()
        formatted_map = repo_map.format_for_prompt(max_tokens=config.repo_map_token_budget)

        # 2. Retrieve top-K relevant files via chosen strategy
        relevant_files = self.retriever.retrieve_relevant_files(
            repo_map=repo_map,
            task_description=task_description,
            strategy=strategy or config.retrieval_strategy,
            top_k=top_k
        )

        event_bus.log(
            "RepoExplorer",
            f"Context engineered: {len(relevant_files)} relevant files identified: {', '.join(relevant_files[:5])}",
            level="INFO"
        )

        return {
            "repo_map": repo_map,
            "formatted_repo_map": formatted_map,
            "relevant_files": relevant_files,
        }
