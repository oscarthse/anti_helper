"""
Project Map - Codebase Context Manager

This module maintains a high-level map of the project structure
that agents can use for context without reading every file.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class FileInfo:
    """Information about a single file."""

    path: str
    language: str | None = None
    size: int = 0
    line_count: int = 0
    last_modified: datetime | None = None
    content_hash: str | None = None

    # Extracted metadata
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "language": self.language,
            "size": self.size,
            "line_count": self.line_count,
            "classes": self.classes,
            "functions": self.functions,
            "imports": self.imports,
        }


@dataclass
class DirectoryInfo:
    """Information about a directory."""

    path: str
    file_count: int = 0
    total_size: int = 0
    subdirectories: list[str] = field(default_factory=list)

    # Inferred purpose
    purpose: str | None = None  # e.g., "tests", "api", "models"


class ProjectMap:
    """
    High-level map of a project's structure.

    Provides agents with architectural context without
    needing to read every file. Can be persisted and updated
    incrementally as files change.
    """

    def __init__(self, root_path: str) -> None:
        self.root_path = Path(root_path)
        self.files: dict[str, FileInfo] = {}
        self.directories: dict[str, DirectoryInfo] = {}
        self.last_scan: datetime | None = None

        # Project metadata
        self.project_type: str | None = None  # python, node, etc.
        self.framework: str | None = None  # fastapi, express, etc.
        self.dependencies: list[str] = []

    async def scan(
        self,
        max_depth: int = 10,
        exclude_patterns: list[str] | None = None,
    ) -> "ProjectMap":
        """
        Scan the project and build the map.

        This is an expensive operation - use refresh() for updates.
        """
        logger.info("project_map_scan", root=str(self.root_path))

        if exclude_patterns is None:
            exclude_patterns = [
                ".git", "node_modules", "__pycache__",
                ".venv", "venv", ".pytest_cache",
                "dist", "build", ".next",
            ]

        self.files.clear()
        self.directories.clear()

        await self._scan_directory(
            self.root_path,
            depth=0,
            max_depth=max_depth,
            exclude_patterns=exclude_patterns,
        )

        self._detect_project_type()
        self.last_scan = datetime.utcnow()

        logger.info(
            "project_map_complete",
            files=len(self.files),
            directories=len(self.directories),
            project_type=self.project_type,
        )

        return self

    async def _scan_directory(
        self,
        dir_path: Path,
        depth: int,
        max_depth: int,
        exclude_patterns: list[str],
    ) -> DirectoryInfo:
        """Recursively scan a directory."""

        if depth > max_depth:
            return DirectoryInfo(path=str(dir_path.relative_to(self.root_path)))

        rel_path = str(dir_path.relative_to(self.root_path))
        if rel_path == ".":
            rel_path = ""

        dir_info = DirectoryInfo(path=rel_path)

        try:
            for item in dir_path.iterdir():
                # Skip excluded patterns
                if any(pattern in str(item) for pattern in exclude_patterns):
                    continue

                if item.is_file():
                    file_info = await self._scan_file(item)
                    self.files[file_info.path] = file_info
                    dir_info.file_count += 1
                    dir_info.total_size += file_info.size

                elif item.is_dir():
                    sub_info = await self._scan_directory(
                        item, depth + 1, max_depth, exclude_patterns
                    )
                    self.directories[sub_info.path] = sub_info
                    dir_info.subdirectories.append(sub_info.path)
                    dir_info.file_count += sub_info.file_count
                    dir_info.total_size += sub_info.total_size

        except PermissionError:
            pass

        # Infer purpose from directory name
        dir_info.purpose = self._infer_purpose(dir_path.name)

        return dir_info

    async def _scan_file(self, file_path: Path) -> FileInfo:
        """Extract metadata from a single file."""

        rel_path = str(file_path.relative_to(self.root_path))
        stat = file_path.stat()

        info = FileInfo(
            path=rel_path,
            language=self._detect_language(file_path.suffix),
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime),
        )

        # For supported languages, extract structure
        if info.language == "python":
            await self._extract_python_structure(file_path, info)

        return info

    async def _extract_python_structure(
        self,
        file_path: Path,
        info: FileInfo,
    ) -> None:
        """Extract classes, functions, and imports from Python file."""

        try:
            import ast

            content = file_path.read_text()
            info.line_count = len(content.splitlines())
            info.content_hash = hashlib.md5(content.encode()).hexdigest()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    info.classes.append(node.name)
                elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    # Only top-level functions
                    if hasattr(node, 'col_offset') and node.col_offset == 0:
                        info.functions.append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        info.imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        info.imports.append(node.module)

        except (SyntaxError, UnicodeDecodeError):
            pass

    def _detect_language(self, suffix: str) -> str | None:
        """Detect programming language from file extension."""

        mapping = {
            ".py": "python",
            ".pyi": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".sql": "sql",
            ".md": "markdown",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
        }

        return mapping.get(suffix.lower())

    def _infer_purpose(self, dir_name: str) -> str | None:
        """Infer directory purpose from name."""

        purposes = {
            "tests": "tests",
            "test": "tests",
            "spec": "tests",
            "api": "api",
            "routes": "api",
            "models": "models",
            "schemas": "schemas",
            "db": "database",
            "database": "database",
            "migrations": "migrations",
            "utils": "utilities",
            "helpers": "utilities",
            "lib": "library",
            "libs": "library",
            "components": "ui",
            "pages": "ui",
            "views": "ui",
            "templates": "templates",
            "static": "static",
            "public": "static",
            "config": "config",
            "settings": "config",
            "docs": "documentation",
            "scripts": "scripts",
        }

        return purposes.get(dir_name.lower())

    def _detect_project_type(self) -> None:
        """Detect the project type based on files present."""

        file_names = set(self.files.keys())

        # Check for Python projects
        if "pyproject.toml" in file_names or "setup.py" in file_names:
            self.project_type = "python"

            # Check for specific frameworks
            if "requirements.txt" in file_names:
                try:
                    reqs = (self.root_path / "requirements.txt").read_text().lower()
                    if "fastapi" in reqs:
                        self.framework = "fastapi"
                    elif "django" in reqs:
                        self.framework = "django"
                    elif "flask" in reqs:
                        self.framework = "flask"
                except:
                    pass

        # Check for Node.js projects
        elif "package.json" in file_names:
            self.project_type = "node"

            try:
                pkg = json.loads((self.root_path / "package.json").read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                if "next" in deps:
                    self.framework = "nextjs"
                elif "react" in deps:
                    self.framework = "react"
                elif "vue" in deps:
                    self.framework = "vue"
                elif "express" in deps:
                    self.framework = "express"
            except:
                pass

    def get_summary(self) -> dict[str, Any]:
        """Get a high-level summary of the project."""

        return {
            "root": str(self.root_path),
            "project_type": self.project_type,
            "framework": self.framework,
            "files": len(self.files),
            "directories": len(self.directories),
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "languages": self._count_languages(),
        }

    def _count_languages(self) -> dict[str, int]:
        """Count files by language."""

        counts: dict[str, int] = {}
        for file_info in self.files.values():
            if file_info.language:
                counts[file_info.language] = counts.get(file_info.language, 0) + 1
        return counts

    def find_related_files(self, file_path: str) -> list[str]:
        """Find files related to a given file (by imports/references)."""

        info = self.files.get(file_path)
        if not info:
            return []

        related = set()

        # Find files that import this one
        module_name = file_path.replace("/", ".").replace(".py", "")
        for path, f_info in self.files.items():
            if any(module_name in imp for imp in f_info.imports):
                related.add(path)

        # Find files this one imports
        for imp in info.imports:
            for path in self.files:
                if imp in path.replace("/", ".").replace(".py", ""):
                    related.add(path)

        return list(related - {file_path})

    def to_context(self, max_tokens: int = 2000) -> str:
        """
        Generate a context string for LLM consumption.

        This provides architectural overview without overwhelming
        the context window.
        """

        lines = [
            f"# Project: {self.root_path.name}",
            f"Type: {self.project_type or 'unknown'}",
            f"Framework: {self.framework or 'none'}",
            "",
            "## Key Directories:",
        ]

        # Add important directories
        for dir_path, dir_info in sorted(self.directories.items()):
            if dir_info.purpose:
                lines.append(f"- {dir_path}/ ({dir_info.purpose}, {dir_info.file_count} files)")

        lines.append("")
        lines.append("## Key Files:")

        # Add important files
        important_files = [
            f for f in self.files.values()
            if f.classes or len(f.functions) > 3
        ]
        for file_info in sorted(important_files, key=lambda f: f.path)[:20]:
            summary = []
            if file_info.classes:
                summary.append(f"classes: {', '.join(file_info.classes[:3])}")
            if file_info.functions:
                summary.append(f"functions: {', '.join(file_info.functions[:5])}")
            lines.append(f"- {file_info.path}: {'; '.join(summary)}")

        context = "\n".join(lines)

        # Truncate if too long (rough token estimate)
        if len(context) > max_tokens * 4:
            context = context[:max_tokens * 4] + "\n... (truncated)"

        return context
