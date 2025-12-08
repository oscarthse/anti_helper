"""
Gravity Guardrails - Symbolic Linter

This module provides deterministic validation logic to intercept
agent-generated code before it is written to disk.

It uses the Abstract Syntax Tree (AST) to:
1. Verify Python syntax correctness.
2. Detect imports of missing dependencies (Symbolic Dependency Check).
"""

import ast
import importlib.util
import sys
from dataclasses import dataclass
from typing import List, Set, Tuple

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LintResult:
    """Result of a linting operation."""
    success: bool
    error: str | None = None
    missing_deps: List[str] | None = None


class GravityLinter:
    """
    Symbolic validator for Python code.

    Serves as a gatekeeper to prevent 'Hallucinated Success' loops
    where agents write broken code that crashes immediately.
    """

    def __init__(self, strict_deps: bool = True) -> None:
        """
        Initialize the linter.

        Args:
            strict_deps: If True, fail validation on missing dependencies.
        """
        self.strict_deps = strict_deps
        # Cache standard library modules to avoid redundant checks
        self.stdlib_modules = sys.stdlib_module_names

    def validate(self, code: str, file_path: str) -> LintResult:
        """
        Validate Python code for syntax and dependencies.

        Args:
            code: The source code to validate.
            file_path: The intended file path (for context).

        Returns:
            LintResult indicating success or failure.
        """
        # 1. Syntax Validtion (AST Parse)
        try:
            tree = ast.parse(code, filename=file_path)
        except SyntaxError as e:
            error_msg = f"SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}"
            logger.warning("linter_syntax_error", file=file_path, error=error_msg)
            return LintResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"AST Parse Error: {str(e)}"
            logger.warning("linter_parse_error", file=file_path, error=error_msg)
            return LintResult(success=False, error=error_msg)

        # 2. Symbolic Dependency Check
        if self.strict_deps:
            missing_deps = self._check_imports(tree)
            if missing_deps:
                error_msg = f"Missing dependencies: {', '.join(missing_deps)}"
                logger.warning("linter_deps_error", file=file_path, missing=missing_deps)
                return LintResult(
                    success=False,
                    error=error_msg,
                    missing_deps=missing_deps
                )

        return LintResult(success=True)

    def _check_imports(self, tree: ast.AST) -> List[str]:
        """
        Walk the AST to find imports and verify they exist in the environment.
        """
        imports = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])

        missing = []
        for module_name in imports:
            if not self._module_exists(module_name):
                missing.append(module_name)

        return missing

    def _module_exists(self, module_name: str) -> bool:
        """Check if a module exists in the current environment."""
        if module_name in self.stdlib_modules:
            return True

        # Special case for local application modules (e.g., 'backend', 'libs')
        # This is a heuristic: assuming project root is in PYTHONPATH or generic top-levels
        # For a more robust check, we'd map the file_path to the project root.
        if module_name in ["backend", "libs", "tests", "gravity_core"]:
            return True

        try:
            return importlib.util.find_spec(module_name) is not None
        except (ImportError, ValueError):
            return False
