"""Configuration management for CodePilot."""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class CodePilotConfig(BaseModel):
    """Configuration settings for CodePilot."""
    
    # LLM Settings
    model_provider: str = Field(default_factory=lambda: os.getenv("CODEPILOT_MODEL_PROVIDER", "google"))
    model_name: str = Field(default_factory=lambda: os.getenv("CODEPILOT_MODEL_NAME", "gemini-3.8-flash"))
    temperature: float = Field(default=0.0)
    
    # GitHub Integration
    github_token: str | None = Field(default_factory=lambda: os.getenv("GITHUB_TOKEN"))
    github_repository: str = Field(default_factory=lambda: os.getenv("GITHUB_REPOSITORY", "devstream-labs/sample-repo"))
    poll_interval_seconds: int = Field(default_factory=lambda: int(os.getenv("CODEPILOT_POLL_INTERVAL", "300")))
    filter_label: str = Field(default_factory=lambda: os.getenv("CODEPILOT_FILTER_LABEL", "ai-assignable"))
    complexity_threshold: int = Field(default_factory=lambda: int(os.getenv("CODEPILOT_COMPLEXITY_THRESHOLD", "7")))
    demo_mode: bool = Field(default_factory=lambda: os.getenv("CODEPILOT_DEMO_MODE", "true").lower() in ("true", "1", "yes"))
    
    # Repo Explorer & Context Engineering
    repo_map_token_budget: int = Field(default_factory=lambda: int(os.getenv("CODEPILOT_TOKEN_BUDGET", "4000")))
    top_k_relevant_files: int = Field(default_factory=lambda: int(os.getenv("CODEPILOT_TOP_K", "10")))
    retrieval_strategy: str = Field(default_factory=lambda: os.getenv("CODEPILOT_RETRIEVAL_STRATEGY", "keyword")) # "keyword" or "embedding"
    
    # Sandboxed Execution & Guardrails
    max_test_retries: int = Field(default=3)
    hitl_retry_threshold: int = Field(default=2)
    max_commit_files: int = Field(default=5)
    default_branch: str = Field(default="main")
    
    # Paths & Directories
    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / ".codepilot_data"
    cache_dir: Path = BASE_DIR / ".codepilot_cache"
    sandbox_root: Path = BASE_DIR / ".codepilot_sandbox"
    memory_store_dir: Path = BASE_DIR / ".codepilot_data" / "memory"
    chroma_db_dir: Path = BASE_DIR / ".codepilot_data" / "chroma"
    skills_dir: Path = BASE_DIR / "codepilot" / "skills"
    
    def ensure_directories(self) -> None:
        """Create necessary directories if they do not exist."""
        for path in (self.data_dir, self.cache_dir, self.sandbox_root, self.memory_store_dir, self.chroma_db_dir):
            path.mkdir(parents=True, exist_ok=True)

config = CodePilotConfig()
config.ensure_directories()
