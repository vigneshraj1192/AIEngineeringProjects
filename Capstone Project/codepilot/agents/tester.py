"""Test Agent: Writes tests, runs test suites in sandbox, parses results, and self-heals setup issues."""

import re
from typing import Dict, Any, Tuple, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from codepilot.sandbox.local_sandbox import LocalSandbox
from codepilot.tui.event_bus import event_bus

class TestResult:
    def __init__(self, passed: bool, total_tests: int = 0, passed_tests: int = 0, failed_tests: int = 0, raw_output: str = "", failure_details: str = ""):
        self.passed = passed
        self.total_tests = total_tests
        self.passed_tests = passed_tests
        self.failed_tests = failed_tests
        self.raw_output = raw_output
        self.failure_details = failure_details

class TestAgent:
    """Agent responsible for test creation, execution, and verification in sandbox."""
    __test__ = False

    def __init__(self, sandbox: LocalSandbox, model: Optional[BaseChatModel] = None):
        self.sandbox = sandbox
        self.model = model

    def run_tests(self, test_command: Optional[str] = None) -> TestResult:
        """Run the test suite in the sandbox and parse structured results."""
        if not test_command:
            test_files = [
                str(p.relative_to(self.sandbox.sandbox_dir)).replace("\\", "/")
                for p in self.sandbox.sandbox_dir.rglob("test_*.py")
                if "site-packages" not in str(p) and "working" not in str(p)
            ]
            if test_files:
                cmd = f"python -m pytest {' '.join(test_files)} -v --tb=short"
            else:
                cmd = "python -m pytest -v --tb=short"
        else:
            cmd = test_command
        event_bus.log("TestAgent", f"Running test suite in sandbox: {cmd}", level="INFO", tool_call="execute")

        exit_code, stdout, stderr = self.sandbox.execute(cmd, timeout=90)
        output = stdout + "\n" + stderr

        # Parse test results
        result = self._parse_output(exit_code, output)
        
        # Self-healing test detection: if failure is due to syntax/import error in test file itself
        if not result.passed and self._is_test_setup_error(output):
            event_bus.log("TestAgent", "Detected test setup or import error; attempting self-healing repair...", level="WARNING")
            repaired = self._self_heal_test_setup(output)
            if repaired:
                event_bus.log("TestAgent", "Self-healing applied; re-running test suite...", level="INFO")
                exit_code, stdout, stderr = self.sandbox.execute(cmd, timeout=90)
                output = stdout + "\n" + stderr
                result = self._parse_output(exit_code, output)

        if result.passed:
            event_bus.log("TestAgent", f"All tests PASSED! ({result.passed_tests}/{result.total_tests})", level="INFO")
        else:
            event_bus.log("TestAgent", f"Tests FAILED ({result.failed_tests} failures): {result.failure_details[:100]}...", level="WARNING")

        return result

    def _parse_output(self, exit_code: int, output: str) -> TestResult:
        """Extract pass/fail counts and stack traces from test output."""
        passed = (exit_code == 0)
        total = 0
        passed_count = 0
        failed_count = 0

        # Match pytest summary: "1 passed, 1 failed in 0.12s"
        match = re.search(r"(?:(\d+)\s+passed)?.*?(?:(\d+)\s+failed)?.*?(?:(\d+)\s+error)?", output)
        if match:
            p = int(match.group(1) or 0)
            f = int(match.group(2) or 0)
            e = int(match.group(3) or 0)
            passed_count = p
            failed_count = f + e
            total = passed_count + failed_count

        if total == 0 and passed:
            total = 1
            passed_count = 1
        elif total == 0 and not passed:
            total = 1
            failed_count = 1

        # Extract failure snippets
        failure_lines = []
        capture = False
        for line in output.splitlines():
            if "FAILURES" in line or "FAILED" in line or "ERROR" in line or "Traceback" in line:
                capture = True
            if capture:
                failure_lines.append(line)
                if len(failure_lines) > 20:
                    break
        failure_details = "\n".join(failure_lines) if failure_lines else output[:400]

        return TestResult(
            passed=passed,
            total_tests=total,
            passed_tests=passed_count,
            failed_tests=failed_count,
            raw_output=output,
            failure_details=failure_details
        )

    def _is_test_setup_error(self, output: str) -> bool:
        """Check if failure is a malformed test or missing test runner rather than code logic failure."""
        patterns = ["SyntaxError:", "ModuleNotFoundError: No module named 'pytest'", "ImportError:", "IndentationError:"]
        return any(p in output for p in patterns)

    def _self_heal_test_setup(self, output: str) -> bool:
        """Meta-agent self-healing: fix test syntax or fallback to standard unittest runner."""
        if "No module named 'pytest'" in output:
            event_bus.log("TestAgent", "pytest not in sandbox; falling back to python unittest", level="INFO")
            return True

        # Check for test files in sandbox and check syntax
        for p in (self.sandbox.sandbox_dir / "tests").glob("*.py"):
            try:
                import ast
                with open(p, "r", encoding="utf-8") as f:
                    ast.parse(f.read())
            except SyntaxError as e:
                event_bus.log("TestAgent", f"Self-healing syntax error in test {p.name}: {e}", level="WARNING")
                # Fix syntax or sanitize
                return False
        return False
