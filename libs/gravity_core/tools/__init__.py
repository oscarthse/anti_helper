"""GravityCore Tools - The Toolset Registry."""

from gravity_core.tools.knowledge import (
    check_dependency_version,
    scrape_web_content,
    web_search_docs,
)
from gravity_core.tools.manipulation import (
    create_new_module,
    edit_file_snippet,
    run_linter_fix,
)
from gravity_core.tools.perception import (
    get_file_signatures,
    scan_repo_structure,
    search_codebase,
)
from gravity_core.tools.registry import ToolRegistry, tool
from gravity_core.tools.runtime import (
    inspect_db_schema,
    read_sandbox_logs,
    run_shell_command,
)
from gravity_core.tools.version_control import (
    git_commit_changes,
    git_diff_staged,
)

__all__ = [
    # Registry
    "ToolRegistry",
    "tool",
    # Knowledge tools
    "web_search_docs",
    "scrape_web_content",
    "check_dependency_version",
    # Perception tools
    "scan_repo_structure",
    "search_codebase",
    "get_file_signatures",
    # Manipulation tools
    "edit_file_snippet",
    "create_new_module",
    "run_linter_fix",
    # Runtime tools
    "run_shell_command",
    "read_sandbox_logs",
    "inspect_db_schema",
    # Version control tools
    "git_commit_changes",
    "git_diff_staged",
]
