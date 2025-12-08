"""
Verified Reality Protocol - Schema Definitions

The "Enforcer" schema that validates file operations on disk before any
event is sent to the UI. If it cannot be validated, it does not exist.
"""

import os
import re
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class FileAction(str, Enum):
    """Types of file operations."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class VerifiedFileAction(BaseModel):
    """
    A file action that has been VERIFIED to exist on disk.

    This model acts as a gatekeeper - instantiation will FAIL if:
    1. The file does not exist on disk
    2. The file is empty (0 bytes)
    3. Python files contain lazy/placeholder code

    Only verified actions can be published to the event bus.
    """

    path: str = Field(description="Absolute path to the file")
    action: FileAction = Field(description="The action that was performed")
    byte_size: int = Field(ge=0, description="Size of the file in bytes")
    step_index: int = Field(ge=0, description="Which step this file belongs to (0-indexed)")
    content_hash: str | None = Field(default=None, description="SHA256 of file content")

    # Validation results (populated by validators)
    quality_checks_passed: list[str] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_reality(self) -> "VerifiedFileAction":
        """
        The Reality Check - validates that the file exists and meets quality standards.

        Raises:
            ValueError: If any validation fails
        """
        # Skip validation for delete actions
        if self.action == FileAction.DELETE:
            return self

        # REALITY CHECK 1: File must exist on disk
        if not os.path.exists(self.path):
            raise ValueError(
                f"Reality Breach: File not found on disk: {self.path}"
            )

        # REALITY CHECK 2: File must not be empty
        file_size = os.path.getsize(self.path)
        if file_size == 0:
            raise ValueError(
                f"Quality Fail: File is empty (0 bytes): {self.path}"
            )

        # Update byte_size from actual file
        object.__setattr__(self, "byte_size", file_size)

        # REALITY CHECK 3: Python-specific quality checks
        if self.path.endswith(".py"):
            self._validate_python_quality()

        return self

    def _validate_python_quality(self) -> None:
        """
        Validate Python file quality - reject lazy/placeholder code.
        """
        try:
            content = Path(self.path).read_text(encoding="utf-8")
        except Exception as e:
            raise ValueError(f"Cannot read file for validation: {e}")

        lines = content.split("\n")

        # Check 1: TODO without real code
        # Allow TODOs if there's actual implementation nearby
        todo_pattern = re.compile(r"#\s*TODO", re.IGNORECASE)
        for i, line in enumerate(lines):
            if todo_pattern.search(line):
                # Check if next 3 lines have actual code (not just pass/...)
                next_lines = lines[i+1:i+4]
                has_implementation = any(
                    l.strip() and
                    l.strip() not in ("pass", "...", "") and
                    not l.strip().startswith("#")
                    for l in next_lines
                )
                if not has_implementation:
                    self.quality_warnings.append(
                        f"Line {i+1}: TODO without implementation"
                    )

        # Check 2: Functions with only 'pass' as body
        pass_only_pattern = re.compile(
            r"def\s+\w+\s*\([^)]*\)\s*(?:->[^:]+)?:\s*\n\s+(?:\"\"\"[^\"]*\"\"\"\s*\n\s+)?pass\s*$",
            re.MULTILINE
        )
        pass_matches = pass_only_pattern.findall(content)
        if pass_matches:
            raise ValueError(
                f"Quality Fail: Function(s) contain only 'pass' - no implementation: {self.path}"
            )

        # Check 3: Functions without return type hints
        # Pattern: def name(args): without ->
        func_pattern = re.compile(r"def\s+(\w+)\s*\([^)]*\)\s*:")
        typed_func_pattern = re.compile(r"def\s+\w+\s*\([^)]*\)\s*->\s*[^:]+:")

        all_funcs = set(func_pattern.findall(content))
        typed_funcs = set()
        for match in typed_func_pattern.finditer(content):
            # Extract function name from typed definition
            func_name = re.search(r"def\s+(\w+)", match.group())
            if func_name:
                typed_funcs.add(func_name.group(1))

        untyped_funcs = all_funcs - typed_funcs - {"__init__", "__str__", "__repr__"}
        if untyped_funcs:
            self.quality_warnings.append(
                f"Functions missing type hints: {', '.join(sorted(untyped_funcs))}"
            )

        # Record passed checks
        self.quality_checks_passed.extend([
            "file_exists",
            "file_not_empty",
            "no_pass_only_functions",
        ])

        if not self.quality_warnings:
            self.quality_checks_passed.append("all_quality_checks_passed")


class VerifiedFileEvent(BaseModel):
    """
    A file event ready to be published to the event bus.

    Wraps VerifiedFileAction with additional event metadata.
    """

    event_type: str = Field(default="file_verified")
    task_id: str = Field(description="UUID of the task")
    step_index: int = Field(description="Which step (for UI progress tracking)")
    action: VerifiedFileAction = Field(description="The verified file action")
    timestamp: str = Field(description="ISO timestamp of the event")

    def to_sse_data(self) -> dict[str, Any]:
        """Convert to SSE-compatible data dict."""
        return {
            "event_type": self.event_type,
            "task_id": self.task_id,
            "step_index": self.step_index,
            "file_path": self.action.path,
            "file_action": self.action.action.value,
            "byte_size": self.action.byte_size,
            "quality_warnings": self.action.quality_warnings,
            "timestamp": self.timestamp,
        }
