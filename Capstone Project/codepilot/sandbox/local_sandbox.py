"""Isolated local sandbox environment for Coder and Test agents."""

import os
import shutil
import difflib
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from codepilot.config import config
from codepilot.guardrails.rules import guardrails, GuardrailViolation
from codepilot.guardrails.hitl import hitl
from codepilot.tui.event_bus import event_bus

class LocalSandbox:
    """
    Isolated directory providing controlled execution and file modification.
    Enforces declarative filesystem permissions:
      - sandbox root: read_write
      - outside sandbox: read_only
    """

    def __init__(self, task_id: str, source_repo: Path, relevant_files: List[str]):
        self.task_id = task_id
        self.source_repo = Path(source_repo).resolve()
        self.relevant_files = relevant_files
        self.sandbox_dir = (config.sandbox_root / task_id).resolve()
        self.working_dir = self.sandbox_dir / "working"
        
        # Track initial file snapshots for diff generation
        self._initial_snapshots: Dict[str, str] = {}
        self._setup_sandbox()

    def _setup_sandbox(self) -> None:
        """Initialize isolated directory and copy subset of relevant files."""
        if self.sandbox_dir.exists():
            shutil.rmtree(self.sandbox_dir, ignore_errors=True)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self.working_dir.mkdir(parents=True, exist_ok=True)

        # Copy only relevant files and essential project config files
        files_to_copy = list(self.relevant_files)
        for cfg_file in ("pyproject.toml", "requirements.txt", "setup.py", "package.json"):
            if (self.source_repo / cfg_file).exists() and cfg_file not in files_to_copy:
                files_to_copy.append(cfg_file)

        for rel_file in files_to_copy:
            src = (self.source_repo / rel_file).resolve()
            if src.exists() and src.is_file():
                dest = self.sandbox_dir / rel_file
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                try:
                    with open(src, "r", encoding="utf-8", errors="replace") as f:
                        self._initial_snapshots[rel_file] = f.read()
                except Exception:
                    self._initial_snapshots[rel_file] = ""

    def _resolve_sandbox_path(self, rel_path: str) -> Path:
        """Resolve path and verify it stays within sandbox boundaries."""
        clean_path = rel_path.lstrip("/\\")
        target = (self.sandbox_dir / clean_path).resolve()
        if not str(target).startswith(str(self.sandbox_dir)):
            raise GuardrailViolation("path_traversal", rel_path, "Attempted access outside sandbox directory")
        return target

    def read_file(self, rel_path: str) -> str:
        """Read file content from within sandbox."""
        target = self._resolve_sandbox_path(rel_path)
        if not target.exists():
            # If not in sandbox yet, attempt to read from source repo if within repo
            src = (self.source_repo / rel_path.lstrip("/\\")).resolve()
            if src.exists() and str(src).startswith(str(self.source_repo)):
                with open(src, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                # Copy into sandbox
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "w", encoding="utf-8") as f:
                    f.write(content)
                self._initial_snapshots[rel_path] = content
                return content
            raise FileNotFoundError(f"File '{rel_path}' not found in sandbox or source repo")

        with open(target, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def write_file(self, rel_path: str, content: str) -> None:
        """Write file in sandbox after verifying file access guardrails."""
        is_valid, reason = guardrails.validate_file_access(rel_path, operation="write")
        if not is_valid:
            event_bus.log("Sandbox", f"Blocked edit on protected file: {rel_path} — {reason}", level="WARNING")
            # Ask human via HITL interrupt
            hitl.request_approval(
                task_id=self.task_id,
                operation=f"Write to sensitive file: {rel_path}",
                reason=reason or "Security guardrail violation on sensitive file pattern",
                details={"file": rel_path}
            )

        target = self._resolve_sandbox_path(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # If this is a newly created file, initial snapshot is empty
        if rel_path not in self._initial_snapshots and not target.exists():
            self._initial_snapshots[rel_path] = ""

        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        event_bus.log("Sandbox", f"Wrote file: {rel_path} ({len(content)} bytes)", level="DEBUG")

    def edit_file(self, rel_path: str, old_str: str, new_str: str) -> bool:
        """Surgically edit file content in sandbox."""
        current_content = self.read_file(rel_path)
        if old_str not in current_content:
            return False
        updated_content = current_content.replace(old_str, new_str, 1)
        self.write_file(rel_path, updated_content)
        return True

    def execute(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        """
        Execute shell command inside sandbox with strict security guardrails.
        Returns (exit_code, stdout, stderr).
        """
        event_bus.log("Sandbox", f"Executing: {command}", level="INFO", tool_call="execute")

        # 1. Guardrail validation
        is_valid, reason = guardrails.validate_command(command, sandbox_dir=str(self.sandbox_dir))
        if not is_valid:
            event_bus.log("Guardrail", f"Blocked execution: {command} — {reason}", level="WARNING")
            # Trigger HITL approval interrupt for blocked operation
            hitl.request_approval(
                task_id=self.task_id,
                operation=f"Execute command: {command}",
                reason=reason or "Dangerous command pattern detected",
                details={"command": command}
            )

        # 2. HITL check for git push
        hitl.check_command_execution(self.task_id, command)

        # 3. Run command in isolated sandbox directory
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = f"{str(self.sandbox_dir)}{os.pathsep}{env.get('PYTHONPATH', '')}"
            process = subprocess.run(
                command,
                shell=True,
                cwd=str(self.sandbox_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            stdout = process.stdout
            stderr = process.stderr
            exit_code = process.returncode
            event_bus.log("Sandbox", f"Command completed with exit code {exit_code}", level="DEBUG")
            return exit_code, stdout, stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return 1, "", str(e)

    def generate_diff(self) -> str:
        """
        Compute unified diff of all modified files against initial snapshots.
        Writes result to working/proposed_diff.txt.
        """
        diff_lines: List[str] = []

        # Find all files in sandbox
        for p in self.sandbox_dir.rglob("*"):
            if p.is_file() and not str(p).startswith(str(self.working_dir)):
                rel_path = str(p.relative_to(self.sandbox_dir)).replace("\\", "/")
                initial = self._initial_snapshots.get(rel_path, "")
                try:
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        current = f.read()
                except Exception:
                    continue

                if initial != current:
                    file_diff = difflib.unified_diff(
                        initial.splitlines(keepends=True),
                        current.splitlines(keepends=True),
                        fromfile=f"a/{rel_path}",
                        tofile=f"b/{rel_path}",
                    )
                    diff_lines.extend(file_diff)

        full_diff = "".join(diff_lines)
        diff_file = self.working_dir / "proposed_diff.txt"
        with open(diff_file, "w", encoding="utf-8") as f:
            f.write(full_diff)

        event_bus.log("Sandbox", f"Generated unified diff ({len(diff_lines)} lines)", level="INFO")
        return full_diff

    def get_modified_files(self) -> List[str]:
        """Return list of relative file paths that differ from initial snapshot."""
        modified = []
        for p in self.sandbox_dir.rglob("*"):
            if p.is_file() and not str(p).startswith(str(self.working_dir)):
                rel_path = str(p.relative_to(self.sandbox_dir)).replace("\\", "/")
                initial = self._initial_snapshots.get(rel_path, "")
                try:
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        current = f.read()
                except Exception:
                    continue
                if initial != current:
                    modified.append(rel_path)
        return modified
