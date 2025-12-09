"""
Manipulation Tools - File editing capabilities.

These tools allow agents to surgically edit code, create new modules,
and run code formatting/linting.
"""

import subprocess
from pathlib import Path

import structlog

from gravity_core.schema import FileOpResult
from gravity_core.tools.registry import tool
from gravity_core.tracking import record_file_change

logger = structlog.get_logger()


@tool(
    name="edit_file_snippet",
    description="Replace text in a file. MUST read file first. Replaces *exact* string match.",
    schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to file"},
            "old_content": {"type": "string", "description": "Exact text to replace"},
            "new_content": {"type": "string", "description": "New text to insert"},
            "occurrence": {
                "type": "integer",
                "description": "Which occurrence to replace (1-indexed)",
                "default": 1,
            },
        },
        "required": ["path", "old_content", "new_content"],
    },
    category="manipulation",
)
async def edit_file_snippet(
    path: str,
    old_content: str,
    new_content: str,
    occurrence: int = 1,
) -> FileOpResult:
    """
    Surgically edit a file by replacing specific content.

    Returns the diff and success status.
    """
    logger.info("edit_file_snippet", path=path, occurrence=occurrence)

    # ---------------------------------------------------------------
    # POLICY CHECK: Read-Before-Write
    # ---------------------------------------------------------------
    from gravity_core.tools.policies import get_current_policy

    policy = get_current_policy()
    if policy:
        if not policy.can_edit(path):
            error_msg = f"Policy Violation: You must read file '{path}' before editing it."
            logger.warning("policy_violation_edit_blocked", path=path)
            return FileOpResult(
                success=False, path=path, operation="edit", error=error_msg, diff=None
            )

    file_path = Path(path)
    if not file_path.exists():
        return FileOpResult(
            success=False, path=path, operation="edit", error=f"File does not exist: {path}"
        )
    try:
        original = file_path.read_text()
    except Exception as e:
        return FileOpResult(
            success=False, path=path, operation="edit", error=f"Could not read file: {e}"
        )

    # Count occurrences
    count = original.count(old_content)
    if count == 0:
        return FileOpResult(
            success=False,
            path=path,
            operation="edit",
            error="Old content not found in file. Hint: Make sure the content matches exactly, including whitespace",
        )

    # Replace content
    if occurrence == 0:
        # Replace all occurrences
        modified = original.replace(old_content, new_content)
    else:
        # Replace specific occurrence
        if occurrence > count:
            return FileOpResult(
                success=False,
                path=path,
                operation="edit",
                error=f"Occurrence {occurrence} not found (only {count} matches)",
            )

        # Find and replace nth occurrence
        idx = -1
        for i in range(occurrence):
            idx = original.find(old_content, idx + 1)

        modified = original[:idx] + new_content + original[idx + len(old_content) :]

    # Write the modified content
    try:
        file_path.write_text(modified, encoding="utf-8")

        # SLEDGEHAMMER VERIFICATION
        if not file_path.exists():
            raise RuntimeError(f"CRITICAL: Edit failed. {file_path} disappeared from disk.")

        if len(modified) > 0 and file_path.stat().st_size == 0:
            raise RuntimeError(f"CRITICAL: Wrote 0 bytes to {file_path} during edit.")

    except Exception as e:
        return FileOpResult(
            success=False, path=path, operation="edit", error=f"Could not save file: {e}"
        )

    # Record metric
    record_file_change(str(file_path.absolute()))

    return FileOpResult(
        success=True,
        path=str(file_path.absolute()),
        operation="edit",
        diff=_generate_diff(original, modified, path),
        size_bytes=len(modified),
        verification_passed=True,
    )


@tool(
    name="create_new_module",
    description="Create a new file or module with proper boilerplate. "
    "Ensures __init__.py files are created for Python packages.",
    schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to create the file at"},
            "content": {"type": "string", "description": "Content to write to the file"},
            "create_init": {
                "type": "boolean",
                "description": "Create __init__.py in parent directories if needed",
                "default": True,
            },
            "overwrite": {
                "type": "boolean",
                "description": "Overwrite if file exists",
                "default": False,
            },
        },
        "required": ["path", "content"],
    },
    category="manipulation",
)
async def create_new_module(
    path: str,
    content: str,
    create_init: bool = True,
    overwrite: bool = False,
) -> FileOpResult:
    """
    Create a new file with proper directory structure.
    """

    logger.info("create_new_module", path=path)

    file_path = Path(path)

    # Check if file exists
    if file_path.exists() and not overwrite:
        return FileOpResult(
            success=False,
            path=path,
            operation="create",
            error=f"File already exists: {path}. Hint: Set overwrite=True to replace existing file",
        )

    # Create parent directories
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        return FileOpResult(
            success=False,
            path=path,
            operation="create",
            error=f"Permission denied creating directory: {e}",
        )

    # Define safe boundaries for __init__.py creation
    # Stop at these directories and don't go above them
    safe_boundaries = {
        Path.home(),
        Path("/"),
        Path("/Users"),
        Path("/home"),
        Path("/tmp"),
        Path("/var"),
    }

    # Create __init__.py files for Python packages (with safety limits)
    init_files_created = []
    if create_init and file_path.suffix == ".py":
        current = file_path.parent
        max_depth = 10  # Safety limit to prevent infinite loops
        depth = 0

        while current != current.parent and depth < max_depth:
            # Stop at safe boundaries
            if current in safe_boundaries or current.resolve() in safe_boundaries:
                break

            # Stop at common project roots
            if (
                (current / "pyproject.toml").exists()
                or (current / "setup.py").exists()
                or (current / ".git").exists()
                or (current / "package.json").exists()
            ):
                break

            init_path = current / "__init__.py"
            if not init_path.exists():
                try:
                    init_path.touch()
                    init_files_created.append(str(init_path))
                except PermissionError:
                    # Can't create here - stop ascending
                    logger.warning("permission_denied_init", path=str(init_path))
                    break

            current = current.parent
            depth += 1

    # Write the file
    try:
        logger.info("create_new_module_writing", path=str(file_path), size=len(content))
        file_path.write_text(content, encoding="utf-8")

        # SLEDGEHAMMER VERIFICATION (Protocol Code Red)
        # 1. Reality Check
        if not file_path.exists():
            raise RuntimeError(
                f"CRITICAL: Write operation failed. {file_path} does not exist on disk."
            )

        # 2. Size Check
        written_size = file_path.stat().st_size
        if len(content) > 0 and written_size == 0:
            raise RuntimeError(
                f"CRITICAL: Wrote 0 bytes to {file_path} but content was not empty. File system may be mocked or corrupted."
            )

    except Exception as e:
        logger.exception("create_new_module_failed_exception", path=path, error=str(e))
        # Ensure we return the error
        return FileOpResult(
            success=False, path=path, operation="create", error=f"Could not write file: {e}"
        )

    # Record metric
    record_file_change(str(file_path.absolute()))
    for init_file in init_files_created:
        record_file_change(init_file)

    return FileOpResult(
        success=True,
        path=str(file_path.absolute()),
        operation="create",
        size_bytes=len(content),
        verification_passed=True,
        data={"init_files_created": init_files_created},
    )


@tool(
    name="run_linter_fix",
    description="Run code linters and formatters to enforce style consistency. "
    "Uses ruff for Python files.",
    schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to file or directory to lint"},
            "fix": {
                "type": "boolean",
                "description": "Automatically fix issues where possible",
                "default": True,
            },
            "format": {"type": "boolean", "description": "Also format the code", "default": True},
        },
        "required": ["path"],
    },
    category="manipulation",
)
async def run_linter_fix(
    path: str,
    fix: bool = True,
    format: bool = True,
) -> dict:
    """
    Run ruff linter and formatter on Python code.
    """
    logger.info("run_linter_fix", path=path, fix=fix, format=format)

    target_path = Path(path)
    if not target_path.exists():
        return {"error": f"Path does not exist: {path}", "success": False}

    results = {
        "lint": None,
        "format": None,
        "success": True,
    }

    # Run ruff check (lint)
    lint_cmd = ["ruff", "check", str(target_path)]
    if fix:
        lint_cmd.append("--fix")

    try:
        lint_result = subprocess.run(
            lint_cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        results["lint"] = {
            "stdout": lint_result.stdout,
            "stderr": lint_result.stderr,
            "exit_code": lint_result.returncode,
        }
    except FileNotFoundError:
        results["lint"] = {"error": "ruff not installed"}
        results["success"] = False
    except subprocess.TimeoutExpired:
        results["lint"] = {"error": "Lint timed out"}
        results["success"] = False

    # Run ruff format
    if format:
        format_cmd = ["ruff", "format", str(target_path)]

        try:
            format_result = subprocess.run(
                format_cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            results["format"] = {
                "stdout": format_result.stdout,
                "stderr": format_result.stderr,
                "exit_code": format_result.returncode,
            }
        except FileNotFoundError:
            results["format"] = {"error": "ruff not installed"}
        except subprocess.TimeoutExpired:
            results["format"] = {"error": "Format timed out"}

    return results


def _generate_diff(original: str, modified: str, filename: str) -> str:
    """Generate a unified diff between original and modified content."""
    import difflib

    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )

    return "".join(diff)
