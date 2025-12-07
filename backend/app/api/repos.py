"""
Repos API - Repository Management

Endpoints for registering and managing repositories.
"""

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import Repository, get_session

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class RepoCreate(BaseModel):
    """Request schema for registering a repository."""

    name: str = Field(description="Display name for the repository")
    path: str = Field(description="Absolute path to the repository")
    description: str | None = Field(
        default=None,
        description="Optional description",
    )


class RepoResponse(BaseModel):
    """Response schema for a repository."""

    id: UUID
    name: str
    path: str
    description: str | None
    project_type: str | None
    framework: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RepoScanResult(BaseModel):
    """Result of scanning a repository."""

    project_type: str | None
    framework: str | None
    file_count: int
    directory_count: int


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
async def register_repository(
    repo_in: RepoCreate,
    session: AsyncSession = Depends(get_session),
) -> Repository:
    """
    Register a repository for agent access.

    This adds the repository to the system and optionally
    scans it to detect project type and framework.
    """
    logger.info("registering_repository", path=repo_in.path)

    # Check if path already registered
    existing = await session.execute(
        select(Repository).where(Repository.path == repo_in.path)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repository at path {repo_in.path} already registered",
        )

    # Verify path exists
    from pathlib import Path
    if not Path(repo_in.path).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path does not exist: {repo_in.path}",
        )

    # Create repository
    repo = Repository(
        name=repo_in.name,
        path=repo_in.path,
        description=repo_in.description,
    )

    session.add(repo)
    await session.flush()
    await session.refresh(repo)

    logger.info("repository_registered", repo_id=str(repo.id))

    return repo


@router.get("/", response_model=list[RepoResponse])
async def list_repositories(
    session: AsyncSession = Depends(get_session),
) -> list[Repository]:
    """List all registered repositories."""

    result = await session.execute(
        select(Repository).order_by(Repository.name)
    )
    return list(result.scalars().all())


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repository(
    repo_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Repository:
    """Get a repository by ID."""

    result = await session.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repo_id} not found",
        )

    return repo


@router.post("/{repo_id}/scan", response_model=RepoScanResult)
async def scan_repository(
    repo_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Scan a repository to detect project type and update metadata.

    This uses the ProjectMap to analyze the codebase structure.
    """
    result = await session.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repo_id} not found",
        )

    # Scan using ProjectMap
    from gravity_core.memory import ProjectMap

    project_map = ProjectMap(repo.path)
    await project_map.scan()

    # Update repository metadata
    repo.project_type = project_map.project_type
    repo.framework = project_map.framework

    logger.info(
        "repository_scanned",
        repo_id=str(repo_id),
        project_type=project_map.project_type,
        framework=project_map.framework,
    )

    return {
        "project_type": project_map.project_type,
        "framework": project_map.framework,
        "file_count": len(project_map.files),
        "directory_count": len(project_map.directories),
    }


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repo_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Unregister a repository.

    This removes the repository from the system but does not
    delete any files on disk.
    """
    result = await session.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repo_id} not found",
        )

    await session.delete(repo)

    logger.info("repository_deleted", repo_id=str(repo_id))
