"""
Perception Tools - Repository Intelligence.

These tools allow agents to understand codebase structure,
search for patterns, and extract code signatures.
"""

import ast
from pathlib import Path

import structlog

from gravity_core.tools.registry import tool

logger = structlog.get_logger()


@tool(
    name="scan_repo_structure",
    description="Get the file tree map of a repository. Provides Architecture context "
    "before reading individual files. Shows directories, files, and sizes.",
    schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Root path to scan"
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum directory depth to scan",
                "default": 4
            },
            "exclude_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Patterns to exclude (e.g., ['.git', 'node_modules', '__pycache__'])"
                ),
                "default": [".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache"]
            }
        },
        "required": ["path"]
    },
    category="perception"
)
async def scan_repo_structure(
    path: str,
    max_depth: int = 4,
    exclude_patterns: list[str] | None = None,
) -> dict:
    """
    Scan repository structure and return file tree.
    """
    logger.info("scan_repo_structure", path=path, max_depth=max_depth)

    if exclude_patterns is None:
        exclude_patterns = [".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache"]

    root = Path(path)
    if not root.exists():
        return {"error": f"Path does not exist: {path}"}

    tree = []
    file_count = 0
    dir_count = 0

    def _should_exclude(p: Path) -> bool:
        return any(pattern in str(p) for pattern in exclude_patterns)

    def _scan_dir(dir_path: Path, depth: int = 0) -> list:
        nonlocal file_count, dir_count

        if depth > max_depth:
            return []

        items = []
        try:
            for item in sorted(dir_path.iterdir()):
                if _should_exclude(item):
                    continue

                if item.is_file():
                    file_count += 1
                    items.append({
                        "type": "file",
                        "name": item.name,
                        "path": str(item.relative_to(root)),
                        "size": item.stat().st_size,
                    })
                elif item.is_dir():
                    dir_count += 1
                    children = _scan_dir(item, depth + 1)
                    items.append({
                        "type": "directory",
                        "name": item.name,
                        "path": str(item.relative_to(root)),
                        "children": children,
                    })
        except PermissionError:
            pass

        return items

    tree = _scan_dir(root)

    return {
        "root": str(root),
        "tree": tree,
        "summary": {
            "files": file_count,
            "directories": dir_count,
        }
    }


@tool(
    name="search_codebase",
    description="Search for patterns in the codebase using grep-like functionality. "
    "Used for impact analysis and finding function usages.",
    schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Root path to search in"
            },
            "pattern": {
                "type": "string",
                "description": "Search pattern (supports regex)"
            },
            "file_pattern": {
                "type": "string",
                "description": "Glob pattern for files to search (e.g., '*.py')",
                "default": "*"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results",
                "default": 50
            },
            "context_lines": {
                "type": "integer",
                "description": "Number of context lines around matches",
                "default": 2
            }
        },
        "required": ["path", "pattern"]
    },
    category="perception"
)
async def search_codebase(
    path: str,
    pattern: str,
    file_pattern: str = "*",
    max_results: int = 50,
    context_lines: int = 2,
) -> dict:
    """
    Search codebase for pattern matches.
    """
    logger.info("search_codebase", path=path, pattern=pattern)

    import re

    root = Path(path)
    if not root.exists():
        return {"error": f"Path does not exist: {path}"}

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return {"error": f"Invalid regex pattern: {e}"}

    matches = []
    files_searched = 0

    # Find matching files
    for file_path in root.rglob(file_pattern):
        if not file_path.is_file():
            continue

        # Skip common non-code directories
        if any(part.startswith('.') or part in ['node_modules', '__pycache__', 'venv', '.venv']
               for part in file_path.parts):
            continue

        files_searched += 1

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.splitlines()

            for i, line in enumerate(lines):
                if regex.search(line):
                    # Get context lines
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    context = lines[start:end]

                    matches.append({
                        "file": str(file_path.relative_to(root)),
                        "line_number": i + 1,
                        "line": line.strip(),
                        "context": "\n".join(context),
                    })

                    if len(matches) >= max_results:
                        return {
                            "matches": matches,
                            "truncated": True,
                            "files_searched": files_searched,
                        }
        except (UnicodeDecodeError, OSError):
            continue

    return {
        "matches": matches,
        "truncated": False,
        "files_searched": files_searched,
    }


@tool(
    name="get_file_signatures",
    description="Extract only class/function definitions from a file. "
    "Gets the 'what' without full implementation, saving tokens on large files.",
    schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to analyze"
            },
            "include_docstrings": {
                "type": "boolean",
                "description": "Include docstrings in output",
                "default": True
            }
        },
        "required": ["path"]
    },
    category="perception"
)
async def get_file_signatures(
    path: str,
    include_docstrings: bool = True,
) -> dict:
    """
    Extract class and function signatures from a Python file.
    """
    logger.info("get_file_signatures", path=path)

    file_path = Path(path)
    if not file_path.exists():
        return {"error": f"File does not exist: {path}"}

    if file_path.suffix != ".py":
        return {"error": "Only Python files are supported currently"}

    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except SyntaxError as e:
        return {"error": f"Syntax error in file: {e}"}

    signatures = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            sig = _extract_class_signature(node, content, include_docstrings)
            signatures.append(sig)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            sig = _extract_function_signature(node, content, include_docstrings)
            signatures.append(sig)

    return {
        "file": path,
        "signatures": signatures,
        "count": len(signatures),
    }


def _extract_class_signature(
    node: ast.ClassDef,
    source: str,
    include_docstrings: bool,
) -> dict:
    """Extract class signature with methods."""

    # Get class docstring
    docstring = None
    if include_docstrings and ast.get_docstring(node):
        docstring = ast.get_docstring(node)

    # Get base classes
    bases = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            bases.append(
                f"{base.value.id}.{base.attr}"
                if isinstance(base.value, ast.Name)
                else base.attr
            )

    # Get method signatures
    methods = []
    for item in node.body:
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
            methods.append(_extract_function_signature(item, source, include_docstrings))

    return {
        "type": "class",
        "name": node.name,
        "bases": bases,
        "docstring": docstring,
        "methods": methods,
        "line": node.lineno,
    }


def _extract_function_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    source: str,
    include_docstrings: bool,
) -> dict:
    """Extract function signature."""

    # Get docstring
    docstring = None
    if include_docstrings and ast.get_docstring(node):
        docstring = ast.get_docstring(node)

    # Get arguments
    args = []
    for arg in node.args.args:
        arg_info = {"name": arg.arg}
        if arg.annotation:
            arg_info["type"] = ast.unparse(arg.annotation)
        args.append(arg_info)

    # Get return type
    return_type = None
    if node.returns:
        return_type = ast.unparse(node.returns)

    # Check if async
    is_async = isinstance(node, ast.AsyncFunctionDef)

    return {
        "type": "function",
        "name": node.name,
        "args": args,
        "return_type": return_type,
        "is_async": is_async,
        "docstring": docstring,
        "line": node.lineno,
    }
