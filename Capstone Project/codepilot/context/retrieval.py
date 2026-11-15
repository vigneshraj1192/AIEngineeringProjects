"""Semantic and keyword retrieval strategies for codebase exploration."""

import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import chromadb
from codepilot.config import config
from codepilot.context.repo_map import RepoMap, FileSummary
from codepilot.tui.event_bus import event_bus

class KeywordRetriever:
    """Fast keyword-based file retrieval using file paths, symbols, and summaries."""

    @staticmethod
    def retrieve(repo_map: RepoMap, query: str, top_k: int = 10) -> List[str]:
        # Extract alphanumeric words from query
        query_terms = set(re.findall(r"[a-zA-Z0-9_]{3,}", query.lower()))
        scores: Dict[str, float] = {}

        for path, summary in repo_map.files.items():
            score = 0.0
            path_lower = path.lower()
            desc_lower = summary.description.lower()
            symbols_lower = [s.lower() for s in summary.symbols]

            for term in query_terms:
                # Direct match in file name has highest weight
                if term in Path(path_lower).name:
                    score += 5.0
                elif term in path_lower:
                    score += 2.5

                # Match in symbols
                for sym in symbols_lower:
                    if term in sym:
                        score += 3.0

                # Match in description
                if term in desc_lower:
                    score += 1.5

            if score > 0:
                scores[path] = score

        sorted_files = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_files = [path for path, _ in sorted_files[:top_k]]
        
        # If no keywords matched, return the most prominent code files (e.g. src/ or root)
        if not top_files and repo_map.files:
            top_files = [p for p in repo_map.files if p.endswith(".py") or p.endswith(".ts") or p.endswith(".js")][:top_k]

        return top_files

class EmbeddingRetriever:
    """Vector-based semantic search over code chunks stored in ChromaDB."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.client = chromadb.PersistentClient(path=str(config.chroma_db_dir.resolve()))
        self.collection_name = f"code_chunks_{config.github_repository.replace('/', '_').replace('-', '_')}"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Semantic code search chunks"}
        )

    def index_repo(self, repo_map: RepoMap) -> None:
        """Chunk and index file contents if not already indexed."""
        if self.collection.count() > 0:
            return

        documents = []
        ids = []
        metadatas = []

        chunk_idx = 0
        for rel_path, summary in repo_map.files.items():
            full_path = self.repo_path / rel_path
            if not full_path.exists() or full_path.stat().st_size > 200_000:
                continue

            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue

            # Split into chunks of ~50 lines
            lines = content.splitlines()
            step = 50
            for i in range(0, max(1, len(lines)), step):
                chunk = "\n".join(lines[i:i + step])
                if not chunk.strip():
                    continue
                cid = f"chunk_{chunk_idx}"
                documents.append(f"File: {rel_path}\nSymbols: {', '.join(summary.symbols)}\nContent:\n{chunk}")
                ids.append(cid)
                metadatas.append({"file_path": rel_path})
                chunk_idx += 1

        if documents:
            # Batch add to ChromaDB
            batch_size = 100
            for b in range(0, len(documents), batch_size):
                self.collection.add(
                    ids=ids[b:b + batch_size],
                    documents=documents[b:b + batch_size],
                    metadatas=metadatas[b:b + batch_size]
                )
            event_bus.log("RepoExplorer", f"Indexed {len(documents)} code chunks into ChromaDB", level="INFO")

    def retrieve(self, query: str, top_k: int = 10) -> List[str]:
        """Perform semantic embedding search and return unique file paths."""
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k * 3, self.collection.count())
        )

        seen = set()
        unique_files = []
        if results and results.get("metadatas") and results["metadatas"][0]:
            for meta in results["metadatas"][0]:
                path = meta.get("file_path")
                if path and path not in seen:
                    seen.add(path)
                    unique_files.append(path)
                    if len(unique_files) >= top_k:
                        break

        return unique_files

class CodeRetriever:
    """Unified retrieval interface supporting both keyword and embedding search."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.keyword = KeywordRetriever()
        self.embedding = EmbeddingRetriever(repo_path)

    def retrieve_relevant_files(
        self,
        repo_map: RepoMap,
        task_description: str,
        strategy: Optional[str] = None,
        top_k: int = 10
    ) -> List[str]:
        strat = strategy or config.retrieval_strategy

        if strat == "embedding":
            try:
                self.embedding.index_repo(repo_map)
                files = self.embedding.retrieve(task_description, top_k=top_k)
                if files:
                    event_bus.log("RepoExplorer", f"Embedding search found {len(files)} files", level="DEBUG")
                    return files
            except Exception as e:
                event_bus.log("RepoExplorer", f"Embedding search failed ({e}); falling back to keyword", level="WARNING")

        files = self.keyword.retrieve(repo_map, task_description, top_k=top_k)
        event_bus.log("RepoExplorer", f"Keyword search found {len(files)} files", level="DEBUG")
        return files
