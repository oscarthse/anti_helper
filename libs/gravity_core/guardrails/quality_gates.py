"""
Quality Gates - Automated Checks for Agent Code.

This module enforces quality standards on code produced by agents
before it is passed to the next stage (e.g., QA).
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from gravity_core.tools.manipulation import run_linter_fix

logger = structlog.get_logger()


@dataclass(frozen=True)
class SelfCheckConfig:
    """Configuration for self-check phase."""

    run_linter: bool = True
    # If True, we try to parse Python files to catch SyntaxErrors
    run_syntax_check: bool = True
    # If True, failing syntax check is a hard failure
    syntax_error_is_blocking: bool = True
    # If True, failing lint (post-fix) is a hard failure (usually False, let QA handle logic bugs)
    lint_error_is_blocking: bool = False


@dataclass
class SelfCheckResult:
    """Result of the self-check process."""

    success: bool
    description: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    files_checked: list[str] = field(default_factory=list)


class CoderSelfCheck:
    """
    Verifies code quality before QA handoff.

    Lifecycle: Created per Coder step, used once, discarded.
    """

    def __init__(self, config: SelfCheckConfig | None = None):
        self.config = config or SelfCheckConfig()

    async def verify(self, files_changed: list[str]) -> SelfCheckResult:
        """
        Run verification on the changed files.

        Args:
            files_changed: List of absolute paths to files modified/created

        Returns:
            SelfCheckResult indicating if code is passable.
        """
        errors = []
        warnings = []
        checked = []

        logger.info("coder_self_check_start", file_count=len(files_changed))

        for file_path_str in files_changed:
            path = Path(file_path_str)
            if not path.exists():
                errors.append(f"File missing: {file_path_str}")
                continue

            checked.append(file_path_str)

            # 1. Syntax Check (Python)
            if self.config.run_syntax_check and path.suffix == ".py":
                syntax_err = self._check_python_syntax(path)
                if syntax_err:
                    msg = f"Syntax Error in {path.name}: {syntax_err}"
                    if self.config.syntax_error_is_blocking:
                        errors.append(msg)
                    else:
                        warnings.append(msg)

            # 2. Linter & Format (Python)
            if self.config.run_linter and path.suffix == ".py":
                # We assume run_linter_fix is an available tool function
                # Since it's async, we await it
                try:
                    # Fix=True, Format=True to auto-polish
                    lint_res = await run_linter_fix(file_path_str, fix=True, format=True)

                    if not lint_res.get("success", False):
                        # If tool execution failed
                        warnings.append(
                            f"Linter tool failed for {path.name}: {lint_res.get('error')}"
                        )
                    else:
                        # Check exit code from ruff
                        lint_data = lint_res.get("lint", {})
                        if lint_data and lint_data.get("exit_code", 0) != 0:
                            msg = f"Linter issues in {path.name} (see logs)"
                            if self.config.lint_error_is_blocking:
                                errors.append(msg)
                            else:
                                warnings.append(msg)

                except Exception as e:
                    warnings.append(f"Linter verification crashed for {path.name}: {e}")

        success = len(errors) == 0

        description = "Self-check passed."
        if not success:
            description = f"Self-check failed with {len(errors)} errors."
        elif warnings:
            description = f"Self-check passed with {len(warnings)} warnings."

        logger.info(
            "coder_self_check_complete", success=success, errors=len(errors), warnings=len(warnings)
        )

        return SelfCheckResult(
            success=success,
            description=description,
            errors=errors,
            warnings=warnings,
            files_checked=checked,
        )

    def _check_python_syntax(self, path: Path) -> str | None:
        """Parse Python file and return error string if invalid."""
        try:
            content = path.read_text(encoding="utf-8")
            ast.parse(content)
            return None
        except SyntaxError as e:
            return f"{e.msg} (line {e.lineno})"
        except Exception as e:
            return f"Unable to parse: {str(e)}"
