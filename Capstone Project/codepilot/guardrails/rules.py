"""Guardrails and safety policies for CodePilot agent execution."""

import re
import fnmatch
from typing import Tuple, Optional
from pathlib import Path

# Blocked command patterns for execute tool
DANGEROUS_COMMAND_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bcurl\b",
    r"\bwget\b",
    r"\bpip\s+install\b",
    r"\bnpm\s+install\s+-g\b",
    r"\bformat\b",
    r"\bdel\s+/[sfq]\b",
    r"\brmdir\s+/[sq]\b",
]

# Blocked sensitive file patterns for file editing
BLOCKED_FILE_PATTERNS = [
    ".env*",
    "*.secret",
    "*.pem",
    "*.key",
    "*credentials*",
    "*id_rsa*",
    "*id_ed25519*",
    "*.pfx",
    "*.p12",
]

class GuardrailViolation(Exception):
    """Raised when an operation violates security guardrails."""
    def __init__(self, operation_type: str, target: str, reason: str):
        super().__init__(f"Guardrail violation [{operation_type}]: {reason} on '{target}'")
        self.operation_type = operation_type
        self.target = target
        self.reason = reason

class GuardrailEngine:
    """Evaluates operations against security guardrails."""

    @staticmethod
    def validate_command(command: str, sandbox_dir: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate shell command.
        Returns (is_valid, violation_reason).
        """
        cmd_lower = command.lower().strip()

        for pattern in DANGEROUS_COMMAND_PATTERNS:
            if re.search(pattern, cmd_lower):
                return False, f"Command contains blocked pattern '{pattern}' (network or destructive command)"

        # Check for path traversal or targeting paths outside sandbox
        if "../.." in command or "/etc" in command or "C:\\Windows" in command:
            return False, "Command targets paths outside the sandbox"

        if sandbox_dir:
            normalized_sandbox = str(Path(sandbox_dir).resolve()).lower()
            # If absolute paths are provided in command, verify they are within sandbox
            for word in command.split():
                if (word.startswith("/") or re.match(r"^[a-zA-Z]:\\", word)) and not word.startswith("-"):
                    try:
                        resolved = str(Path(word).resolve()).lower()
                        if not resolved.startswith(normalized_sandbox):
                            return False, f"Command targets path '{word}' outside sandbox directory"
                    except Exception:
                        pass

        return True, None

    @staticmethod
    def validate_file_access(file_path: str, operation: str = "write") -> Tuple[bool, Optional[str]]:
        """
        Validate file access or edit.
        Returns (is_valid, violation_reason).
        """
        path_obj = Path(file_path)
        file_name = path_obj.name.lower()

        # Check sensitive file patterns
        for pattern in BLOCKED_FILE_PATTERNS:
            if fnmatch.fnmatch(file_name, pattern):
                return False, f"File matches blocked sensitive file pattern '{pattern}'"

        return True, None

guardrails = GuardrailEngine()
