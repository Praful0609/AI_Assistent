"""
Pydantic v2 schemas for Projects API.
Separate from ORM models to keep request/response shapes explicit.
"""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.models.project import ProjectStatus, SourceType, Language


# ── Project Schemas ───────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    """Body for POST /projects/upload when providing a Git URL."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    git_url: str = Field(..., description="Public Git repository URL")


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None
    source_type: SourceType
    source_url: str | None
    status: ProjectStatus
    total_files: int
    total_lines: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int


# ── Analysis Run Schemas ──────────────────────────────────────────────────────

class AnalysisRunResponse(BaseModel):
    id: str
    project_id: str
    status: str
    progress: int
    error: str | None
    meta: dict[str, Any] | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── File Schemas ──────────────────────────────────────────────────────────────

class SourceFileResponse(BaseModel):
    id: str
    path: str
    language: Language
    size_bytes: int
    line_count: int
    is_parsed: bool
    is_indexed: bool

    model_config = {"from_attributes": True}


class FileListResponse(BaseModel):
    files: list[SourceFileResponse]
    total: int
    languages: dict[str, int]  # {language: count}


# ── Upload Response ───────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    project_id: str
    analysis_run_id: str
    message: str = "Project queued for analysis"
