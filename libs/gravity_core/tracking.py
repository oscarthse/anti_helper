"""
Execution Tracking Context

This module provides context variables to track agent actions across tool calls.
It is used to collect metrics like files changed, fix attempts, etc.
"""

from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class ExecutionMetrics:
    files_changed: set[str] = field(default_factory=set)
    fix_attempts: int = 0


_metrics_context: ContextVar[ExecutionMetrics] = ContextVar(
    "execution_metrics", default=ExecutionMetrics()
)


def get_current_metrics() -> ExecutionMetrics:
    """Get the current execution metrics."""
    return _metrics_context.get()


def record_file_change(path: str) -> None:
    """Record that a file was changed."""
    metrics = get_current_metrics()
    metrics.files_changed.add(path)


def record_fix_attempt() -> None:
    """Record a fix attempt (e.g., self-correction)."""
    metrics = get_current_metrics()
    metrics.fix_attempts += 1
