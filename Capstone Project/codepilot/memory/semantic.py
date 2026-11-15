"""Semantic memory management for cross-session persistent lessons learned via ChromaDB."""

import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import chromadb
from codepilot.config import config

class LessonLearned(BaseModel):
    """Structured lesson learned from a successfully solved task or merged PR."""
    id: str
    repository: str
    issue_number: int
    issue_title: str
    task_type: str
    files_modified: List[str] = Field(default_factory=list)
    approach: str
    lesson_text: str
    timestamp: float = Field(default_factory=time.time)

class SemanticMemoryStore:
    """Persistent vector store for engineering knowledge and past solutions."""
    
    def __init__(self, persist_dir: Path = config.chroma_db_dir):
        self.persist_dir = persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir.resolve()))
        self.collection = self.client.get_or_create_collection(
            name="codepilot_lessons_learned",
            metadata={"description": "Cross-session persistent lessons learned across repositories"}
        )
        self._seed_default_lessons_if_empty()

    def _seed_default_lessons_if_empty(self) -> None:
        """Seed baseline engineering patterns if database is newly initialized."""
        if self.collection.count() == 0:
            seed_lessons = [
                {
                    "id": "seed_1",
                    "repo": "devstream-labs/sample-repo",
                    "issue_num": 101,
                    "title": "OAuth redirect URL with query params causes 400 bad request",
                    "task_type": "bug_fix",
                    "files": ["src/auth/oauth.py", "tests/test_oauth.py"],
                    "approach": "URL-encode the redirect_uri parameter using urllib.parse.quote before constructing authorization URL.",
                    "document": "Issue #101: OAuth redirect_uri query params. Always URL-encode query parameters in OAuth callback redirect URLs using urllib.parse.quote."
                },
                {
                    "id": "seed_2",
                    "repo": "devstream-labs/sample-repo",
                    "issue_num": 102,
                    "title": "Add JSON schema validation for incoming webhook payloads",
                    "task_type": "feature_addition",
                    "files": ["src/webhooks/validator.py", "tests/test_webhooks.py"],
                    "approach": "Use Pydantic v2 BaseModel with ValidationError handling to return structured 422 Unprocessable Entity responses.",
                    "document": "Issue #102: Webhook validation. Validate payload using Pydantic BaseModel and catch ValidationError to return structured 422 JSON."
                },
                {
                    "id": "seed_3",
                    "repo": "devstream-labs/sample-repo",
                    "issue_num": 103,
                    "title": "Upgrade requests library and resolve timeout keyword parameter deprecation",
                    "task_type": "dependency_update",
                    "files": ["pyproject.toml", "src/client/http.py"],
                    "approach": "Explicitly set timeout tuples (connect, read) on all Session requests to prevent indefinite hangs.",
                    "document": "Issue #103: Requests upgrade and timeout deprecation. Always configure explicit connect and read timeouts on client requests."
                }
            ]
            ids = [s["id"] for s in seed_lessons]
            documents = [s["document"] for s in seed_lessons]
            metadatas = [
                {
                    "repository": s["repo"],
                    "issue_number": s["issue_num"],
                    "issue_title": s["title"],
                    "task_type": s["task_type"],
                    "files_modified": ",".join(s["files"]),
                    "approach": s["approach"]
                }
                for s in seed_lessons
            ]
            self.collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def record_lesson(
        self,
        repository: str,
        issue_number: int,
        issue_title: str,
        task_type: str,
        files_modified: List[str],
        approach: str,
    ) -> LessonLearned:
        """Store a new lesson learned from a resolved task in ChromaDB."""
        lesson_id = f"lesson_{issue_number}_{int(time.time())}"
        lesson_text = (
            f"Repository: {repository} | Issue #{issue_number}: {issue_title}\n"
            f"Type: {task_type}\n"
            f"Files: {', '.join(files_modified)}\n"
            f"Successful Approach: {approach}"
        )
        metadata = {
            "repository": repository,
            "issue_number": issue_number,
            "issue_title": issue_title,
            "task_type": task_type,
            "files_modified": ",".join(files_modified),
            "approach": approach,
        }
        self.collection.add(
            ids=[lesson_id],
            documents=[lesson_text],
            metadatas=[metadata]
        )
        return LessonLearned(
            id=lesson_id,
            repository=repository,
            issue_number=issue_number,
            issue_title=issue_title,
            task_type=task_type,
            files_modified=files_modified,
            approach=approach,
            lesson_text=lesson_text,
        )

    def retrieve_relevant_lessons(
        self,
        repository: str,
        query: str,
        task_type: Optional[str] = None,
        top_k: int = 3
    ) -> List[LessonLearned]:
        """Retrieve the top-K most similar past lessons."""
        if self.collection.count() == 0:
            return []

        where_filter = None
        if task_type:
            where_filter = {"task_type": task_type}

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=min(top_k, self.collection.count()),
                where=where_filter
            )
        except Exception:
            # Fallback if where filter restricts to 0 matches
            results = self.collection.query(
                query_texts=[query],
                n_results=min(top_k, self.collection.count())
            )

        lessons = []
        if results and results.get("ids") and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                doc = results["documents"][0][i]
                meta = results["metadatas"][0][i]
                lesson_id = results["ids"][0][i]
                files = meta.get("files_modified", "").split(",") if meta.get("files_modified") else []
                lessons.append(LessonLearned(
                    id=lesson_id,
                    repository=meta.get("repository", repository),
                    issue_number=int(meta.get("issue_number", 0)),
                    issue_title=meta.get("issue_title", ""),
                    task_type=meta.get("task_type", ""),
                    files_modified=[f.strip() for f in files if f.strip()],
                    approach=meta.get("approach", ""),
                    lesson_text=doc,
                ))
        return lessons

    def format_lessons_for_prompt(self, lessons: List[LessonLearned]) -> str:
        """Format retrieved lessons into prompt context for Coder agent."""
        if not lessons:
            return "No prior lessons found for this issue type."
        
        parts = ["=== PRIOR LESSONS LEARNED (SEMANTIC MEMORY) ==="]
        for idx, lesson in enumerate(lessons):
            parts.append(
                f"\nLesson {idx+1} [Issue #{lesson.issue_number} - {lesson.issue_title}]:\n"
                f"Files modified: {', '.join(lesson.files_modified)}\n"
                f"Approach that worked: {lesson.approach}"
            )
        return "\n".join(parts)

semantic_memory = SemanticMemoryStore()
