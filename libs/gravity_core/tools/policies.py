"""
File Access Policy - Abstraction for tracking file reads.

Enforces "read-before-write" patterns to ensure agents
read files before attempting modifications.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import structlog

logger = structlog.get_logger()


@dataclass
class FileAccessPolicy:
    """
    Tracks which files have been read to enforce read-before-write.

    Instance is scoped to a single TaskStep. Created by TaskExecutor
    before each step and reset afterwards.

    Design Notes:
    - Paths are normalized to absolute, resolved form for consistency
    - Policy is non-blocking for create operations (new files)
    - Edit operations require prior read

    Usage:
        policy = FileAccessPolicy()
        policy.record_read("/path/to/file.py")
        assert policy.can_edit("/path/to/file.py")  # True
        assert policy.can_edit("/path/to/other.py")  # False
    """

    _read_files: set[str] = field(default_factory=set)

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path to absolute, resolved form.

        Handles:
        - Relative paths
        - Symlinks
        - Trailing slashes
        - Case sensitivity (OS-dependent)
        """
        try:
            abs_path = Path(path).resolve().as_posix()
            return abs_path
        except Exception as e:
            logger.warning("path_normalization_failed", path=path, error=str(e))
            # Fall back to basic absolute path
            return os.path.abspath(path)

    def record_read(self, path: str) -> None:
        """
        Record that a file has been read.

        Args:
            path: Path to the file that was read
        """
        normalized = self._normalize_path(path)
        self._read_files.add(normalized)
        logger.debug("file_read_recorded", path=normalized)

    def can_edit(self, path: str) -> bool:
        """
        Check if a file can be edited (was previously read).

        Args:
            path: Path to the file to check

        Returns:
            True if file was read and can be edited
        """
        normalized = self._normalize_path(path)
        allowed = normalized in self._read_files
        if not allowed:
            logger.debug(
                "edit_blocked_no_read",
                path=normalized,
                read_files_count=len(self._read_files),
            )
        return allowed

    def can_create(self, path: str) -> bool:
        """
        Check if a file can be created.

        New files don't require prior read - this is always True.

        Args:
            path: Path to the file to create

        Returns:
            Always True (create doesn't require read)
        """
        return True

    def reset(self) -> None:
        """Clear all recorded reads (for step boundaries)."""
        count = len(self._read_files)
        self._read_files.clear()
        logger.debug("file_access_policy_reset", cleared_count=count)

    @property
    def read_files_count(self) -> int:
        """Return count of files that have been read."""
        return len(self._read_files)

    @property
    def read_files(self) -> frozenset[str]:
        """Return immutable copy of read files (for debugging/testing)."""
        return frozenset(self._read_files)


# -------------------------------------------------------------------
# Global Policy Management (ContextVars)
# -------------------------------------------------------------------

import contextvars

# The ContextVar holds the *active* FileAccessPolicy for the current async context
_policy_ctx: contextvars.ContextVar[FileAccessPolicy | None] = contextvars.ContextVar(
    "file_access_policy", default=None
)


def set_current_policy(policy: FileAccessPolicy | None) -> None:
    """
    Set the current file access policy for this context.

    Called by TaskExecutor before executing a step.

    Args:
        policy: The policy to use, or None to clear
    """
    # ContextVars are set for the current context and its children
    _token = _policy_ctx.set(policy)  # noqa: F841
    # We generally don't need the token unless we're doing manual resets within
    # the same context, but for TaskStep boundaries, setting a new value is fine.

    if policy:
        logger.debug("file_access_policy_set")
    else:
        logger.debug("file_access_policy_cleared")


def get_current_policy() -> FileAccessPolicy | None:
    """
    Get the current file access policy.

    Returns:
        Current policy, or None if not set (enforcement disabled)
    """
    return _policy_ctx.get()


def clear_current_policy() -> None:
    """Clear the current policy."""
    set_current_policy(None)
