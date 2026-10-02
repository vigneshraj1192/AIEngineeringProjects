"""Repo Map construction, token budgeting, and caching."""

import os
import ast
import json
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from pydantic import BaseModel, Field
from codepilot.config import config
from codepilot.tui.event_bus import event_bus

class FileSummary(BaseModel):
    """Structural summary of a single file in the repository."""
    path: str
    language: str
    line_count: int
    symbols: List[str] = Field(default_factory=list)
    description: str = ""

class RepoMap(BaseModel):
    """Compressed repository representation fitting within token budget."""
    root_path: str
    tree_text: str
    files: Dict[str, FileSummary] = Field(default_factory=dict)
    token_estimate: int = 0
    cache_hash: str = ""

    def format_for_prompt(self, max_tokens: int = 4000) -> str:
        """Render formatted repo map string within token budget."""
        header = f"=== REPOSITORY MAP (Budget: {max_tokens} tokens) ===\n\nDirectory Tree:\n{self.tree_text}\n\nFile Summaries:\n"
        
        file_lines = []
        for path, summary in sorted(self.files.items()):
            syms = f" | symbols: {', '.join(summary.symbols[:8])}" if summary.symbols else ""
            desc = f" — {summary.description}" if summary.description else ""
            file_lines.append(f"- {path} ({summary.language}, {summary.line_count} lines){syms}{desc}")

        body = "\n".join(file_lines)
        full_text = header + body

        # Estimate tokens (approx 1 token per 3.8 chars)
        est_tokens = len(full_text) // 4
        if est_tokens <= max_tokens:
            return full_text

        # Truncate aggressively if exceeding budget
        truncated_lines = []
        for line in file_lines:
            # Strip symbol details to save budget
            stripped = line.split(" | symbols:")[0]
            truncated_lines.append(stripped)
            current_est = (len(header) + len("\n".join(truncated_lines))) // 4
            if current_est >= max_tokens - 100:
                truncated_lines.append("... [remaining file summaries truncated to satisfy token budget]")
                break

        return header + "\n".join(truncated_lines)

class RepoMapBuilder:
    """Recursively walks repository, extracts symbols, and manages caching."""

    IGNORE_DIRS = {
        ".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache",
        ".codepilot_cache", ".codepilot_sandbox", ".codepilot_data", "dist", "build", ".idea"
    }

    IGNORE_EXTS = {
        ".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".tar", ".gz",
        ".sqlite", ".db", ".exe", ".dll", ".so", ".bin", ".lock"
    }

    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path).resolve()
        self.cache_file = config.cache_dir / f"repo_map_{self._repo_id()}.json"

    def _repo_id(self) -> str:
        return hashlib.md5(str(self.repo_path).encode("utf-8")).hexdigest()[:10]

    def _compute_repo_hash(self) -> str:
        """Compute quick hash based on git diff or directory mtimes."""
        try:
            # Try git diff or git rev-parse if git repo
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=5
            )
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                content = f"{head.stdout}_{res.stdout}"
                return hashlib.md5(content.encode("utf-8")).hexdigest()
        except Exception:
            pass

        # Fallback to file mtimes
        mtimes = []
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            for file in files:
                ext = Path(file).suffix.lower()
                if ext not in self.IGNORE_EXTS:
                    try:
                        p = Path(root) / file
                        mtimes.append(f"{file}_{p.stat().st_mtime}")
                    except Exception:
                        pass
        return hashlib.md5("".join(mtimes[:500]).encode("utf-8")).hexdigest()

    def _parse_python_file(self, content: str) -> Tuple[List[str], str]:
        """Extract classes, functions, and module docstring using AST."""
        symbols = []
        description = ""
        try:
            tree = ast.parse(content)
            description = (ast.get_docstring(tree) or "").split("\n")[0].strip()
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(f"{node.name}()")
                elif isinstance(node, ast.ClassDef):
                    symbols.append(f"class {node.name}")
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            symbols.append(f"{node.name}.{item.name}()")
                            symbols.append(f"{item.name}()")
        except Exception:
            pass
        return symbols, description

    def build_or_load(self, force_refresh: bool = False) -> RepoMap:
        """Load cached Repo Map or build fresh if changed."""
        current_hash = self._compute_repo_hash()
        
        if not force_refresh and self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("cache_hash") == current_hash:
                        event_bus.log("RepoExplorer", "Loaded cached Repo Map from disk", level="DEBUG")
                        return RepoMap(**data)
            except Exception:
                pass

        event_bus.log("RepoExplorer", f"Building Repo Map for {self.repo_path.name}...", level="INFO")
        repo_map = self._build_fresh(current_hash)

        # Cache to disk
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                f.write(repo_map.model_dump_json(indent=2))
        except Exception as e:
            event_bus.log("RepoExplorer", f"Failed to cache repo map: {e}", level="WARNING")

        return repo_map

    def _build_fresh(self, current_hash: str) -> RepoMap:
        tree_lines = []
        files_dict: Dict[str, FileSummary] = {}

        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = sorted([d for d in dirs if d not in self.IGNORE_DIRS])
            rel_dir = os.path.relpath(root, self.repo_path)
            depth = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
            indent = "  " * depth

            if rel_dir != ".":
                tree_lines.append(f"{indent}📁 {os.path.basename(root)}/")

            for file in sorted(files):
                ext = Path(file).suffix.lower()
                if ext in self.IGNORE_EXTS:
                    continue

                full_path = Path(root) / file
                rel_path = str(full_path.relative_to(self.repo_path)).replace("\\", "/")
                file_indent = "  " * (depth + 1)
                tree_lines.append(f"{file_indent}📄 {file}")

                lang = "python" if ext == ".py" else ("javascript" if ext in (".js", ".jsx") else ("typescript" if ext in (".ts", ".tsx") else ("markdown" if ext == ".md" else "text")))
                
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    line_count = len(content.splitlines())
                except Exception:
                    content = ""
                    line_count = 0

                symbols, desc = [], ""
                if lang == "python":
                    symbols, desc = self._parse_python_file(content)
                elif lang in ("javascript", "typescript"):
                    # Quick regex symbols for JS/TS
                    import re
                    fn_matches = re.findall(r"(?:function\s+([a-zA-Z0-9_]+)|const\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\()", content)
                    symbols = [m[0] or m[1] for m in fn_matches if (m[0] or m[1])]
                    desc = f"JavaScript/TypeScript source ({len(symbols)} functions)"

                files_dict[rel_path] = FileSummary(
                    path=rel_path,
                    language=lang,
                    line_count=line_count,
                    symbols=symbols,
                    description=desc
                )

        tree_text = "\n".join(tree_lines[:250]) # bound tree lines
        formatted = f"{tree_text}\n" + json.dumps({k: v.model_dump() for k, v in files_dict.items()})
        est_tokens = len(formatted) // 4

        return RepoMap(
            root_path=str(self.repo_path),
            tree_text=tree_text,
            files=files_dict,
            token_estimate=est_tokens,
            cache_hash=current_hash
        )
