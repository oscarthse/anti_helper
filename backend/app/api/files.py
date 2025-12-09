import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Repository
from backend.app.db.session import get_session

router = APIRouter(prefix="/files", tags=["files"])


class FileNode(BaseModel):
    name: str
    path: str
    type: str  # "file" or "directory"
    children: list["FileNode"] | None = None


@router.get("/tree", response_model=list[FileNode])
async def get_file_tree(repo_id: UUID, session: AsyncSession = Depends(get_session)):
    """
    Get the REAL file structure from the OS.
    Protocol: Deterministic Reality.
    """

    # 1. Fetch Repo Path
    stmt = select(Repository).where(Repository.id == repo_id)
    result = await session.execute(stmt)
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if not os.path.exists(repo.path):
        raise HTTPException(
            status_code=400, detail=f"Repository path does not exist on disk: {repo.path}"
        )

    # 2. Build Tree
    # Helper to recursively build tree
    def build_tree(current_path: str) -> list[FileNode]:
        nodes = []
        try:
            # Sort: Directories first, then files
            entries = sorted(
                os.scandir(current_path), key=lambda e: (not e.is_dir(), e.name.lower())
            )

            for entry in entries:
                # Ignore hidden files/dirs and common junk
                if entry.name.startswith("."):
                    continue
                if entry.name in ["__pycache__", "node_modules", "venv", "env", "dist", "build"]:
                    continue

                node = FileNode(
                    name=entry.name,
                    path=entry.path,  # Absolute path for now
                    type="directory" if entry.is_dir() else "file",
                    children=build_tree(entry.path) if entry.is_dir() else None,
                )
                nodes.append(node)

        except PermissionError:
            pass  # Skip unreadable

        return nodes

    return build_tree(repo.path)
