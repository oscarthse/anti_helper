"""
Version Control Tools - Git operations.

These tools allow agents to commit changes and review diffs
before finalizing modifications.
"""

import subprocess
from pathlib import Path
from typing import Optional

import structlog

from gravity_core.tools.registry import tool

logger = structlog.get_logger()


@tool(
    name="git_commit_changes",
    description="Commit staged changes with a structured commit message. "
    "Forces consistent commit message format.",
    schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository path"
            },
            "message": {
                "type": "string",
                "description": "Commit message (will be formatted)"
            },
            "type": {
                "type": "string",
                "description": "Commit type: feat, fix, refactor, docs, test, chore",
                "enum": ["feat", "fix", "refactor", "docs", "test", "chore"],
                "default": "feat"
            },
            "scope": {
                "type": "string",
                "description": "Optional scope (e.g., 'api', 'ui', 'core')"
            },
            "stage_all": {
                "type": "boolean",
                "description": "Stage all changes before committing",
                "default": False
            }
        },
        "required": ["path", "message"]
    },
    category="version_control"
)
async def git_commit_changes(
    path: str,
    message: str,
    type: str = "feat",
    scope: Optional[str] = None,
    stage_all: bool = False,
) -> dict:
    """
    Commit changes with a structured commit message.

    Uses Conventional Commits format: type(scope): message
    """
    logger.info("git_commit_changes", path=path, type=type)

    repo_path = Path(path)
    if not repo_path.exists():
        return {"error": f"Path does not exist: {path}", "success": False}

    # Check if it's a git repository
    if not (repo_path / ".git").exists():
        return {"error": "Not a git repository", "success": False}

    # Stage all if requested
    if stage_all:
        stage_result = subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if stage_result.returncode != 0:
            return {
                "error": f"Failed to stage: {stage_result.stderr}",
                "success": False,
            }

    # Check if there are staged changes
    status_result = subprocess.run(
        ["git", "diff", "--cached", "--stat"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if not status_result.stdout.strip():
        return {
            "error": "No staged changes to commit",
            "success": False,
        }

    # Format commit message
    if scope:
        formatted_message = f"{type}({scope}): {message}"
    else:
        formatted_message = f"{type}: {message}"

    # Commit
    commit_result = subprocess.run(
        ["git", "commit", "-m", formatted_message],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if commit_result.returncode != 0:
        return {
            "error": f"Commit failed: {commit_result.stderr}",
            "success": False,
        }

    # Get the commit hash
    hash_result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    commit_hash = hash_result.stdout.strip()

    return {
        "success": True,
        "commit_hash": commit_hash,
        "message": formatted_message,
        "files_changed": status_result.stdout,
    }


@tool(
    name="git_diff_staged",
    description="Show the diff of staged changes. "
    "Allows the agent to review changes before finalizing.",
    schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository path"
            },
            "file_path": {
                "type": "string",
                "description": "Specific file to diff (optional)"
            },
            "context_lines": {
                "type": "integer",
                "description": "Lines of context around changes",
                "default": 3
            }
        },
        "required": ["path"]
    },
    category="version_control"
)
async def git_diff_staged(
    path: str,
    file_path: Optional[str] = None,
    context_lines: int = 3,
) -> dict:
    """
    Get the diff of staged changes.

    This is the Self-Correction mechanism - agents review their
    changes before committing.
    """
    logger.info("git_diff_staged", path=path, file=file_path)

    repo_path = Path(path)
    if not repo_path.exists():
        return {"error": f"Path does not exist: {path}", "success": False}

    # Build command
    cmd = ["git", "diff", "--cached", f"-U{context_lines}"]
    if file_path:
        cmd.append(file_path)

    result = subprocess.run(
        cmd,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return {
            "error": f"git diff failed: {result.stderr}",
            "success": False,
        }

    diff = result.stdout

    # Get stat summary
    stat_result = subprocess.run(
        ["git", "diff", "--cached", "--stat"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    # Count files and lines
    files_changed = []
    insertions = 0
    deletions = 0

    for line in diff.split("\n"):
        if line.startswith("+++ b/"):
            files_changed.append(line[6:])
        elif line.startswith("+") and not line.startswith("+++"):
            insertions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1

    return {
        "success": True,
        "diff": diff,
        "stat": stat_result.stdout,
        "summary": {
            "files_changed": len(files_changed),
            "insertions": insertions,
            "deletions": deletions,
        },
        "files": files_changed,
    }
