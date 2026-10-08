"""
SQLAlchemy ORM models for project metadata.
Designed for single-user MVP; owner_id column is nullable now
and will be non-nullable when multi-user auth is added.
"""
import uuid
from datetime import datetime, UTC
from enum import Enum as PyEnum

from sqlalchemy import (
    String, Text, Integer, BigInteger, Boolean,
    DateTime, ForeignKey, Enum as SAEnum, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enumerations ──────────────────────────────────────────────────────────────

class ProjectStatus(str, PyEnum):
    PENDING   = "pending"
    PARSING   = "parsing"
    ANALYZING = "analyzing"
    INDEXING  = "indexing"
    COMPLETE  = "complete"
    FAILED    = "failed"


class SourceType(str, PyEnum):
    GIT_URL = "git_url"
    ZIP     = "zip"


class Language(str, PyEnum):
    PYTHON     = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA       = "java"
    GO         = "go"
    RUST       = "rust"
    CPP        = "cpp"
    CSHARP     = "csharp"
    RUBY       = "ruby"
    UNKNOWN    = "unknown"


# ── Models ────────────────────────────────────────────────────────────────────

class Project(Base):
    """
    Top-level project entity.

    NOTE: owner_id is nullable for the single-user MVP. When JWT auth is
    introduced (Phase 2 scale-up), set nullable=False and add a User model.
    """
    __tablename__ = "projects"

    id:         Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    name:       Mapped[str]      = mapped_column(String(255), nullable=False)
    description:Mapped[str|None] = mapped_column(Text, nullable=True)
    source_type:Mapped[SourceType] = mapped_column(SAEnum(SourceType), nullable=False)
    source_url: Mapped[str|None] = mapped_column(Text, nullable=True)   # git URL
    status:     Mapped[ProjectStatus] = mapped_column(
                    SAEnum(ProjectStatus), nullable=False, default=ProjectStatus.PENDING
                )
    # Multi-user hook: nullable for now
    owner_id:   Mapped[str|None] = mapped_column(String(36), nullable=True, index=True)

    # Storage
    upload_path: Mapped[str|None] = mapped_column(Text, nullable=True)  # path on disk
    total_files: Mapped[int]     = mapped_column(Integer, default=0)
    total_lines: Mapped[int]     = mapped_column(BigInteger, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    # Relationships
    files:        Mapped[list["SourceFile"]]  = relationship(back_populates="project", cascade="all, delete-orphan")
    analysis_runs:Mapped[list["AnalysisRun"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class AnalysisRun(Base):
    """Tracks a single analysis pass over a project."""
    __tablename__ = "analysis_runs"

    id:         Mapped[str]  = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str]  = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    status:     Mapped[str]  = mapped_column(String(50), default="pending")
    celery_task_id: Mapped[str|None] = mapped_column(String(255), nullable=True)
    error:      Mapped[str|None]     = mapped_column(Text, nullable=True)
    progress:   Mapped[int]          = mapped_column(Integer, default=0)   # 0–100
    meta:       Mapped[dict|None]    = mapped_column(JSON, nullable=True)   # arbitrary step info

    started_at:   Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:   Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped["Project"] = relationship(back_populates="analysis_runs")


class SourceFile(Base):
    """A single source file belonging to a project."""
    __tablename__ = "source_files"

    id:         Mapped[str]  = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str]  = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    path:       Mapped[str]  = mapped_column(Text, nullable=False)     # relative to project root
    language:   Mapped[Language] = mapped_column(SAEnum(Language), default=Language.UNKNOWN)
    size_bytes: Mapped[int]  = mapped_column(BigInteger, default=0)
    line_count: Mapped[int]  = mapped_column(Integer, default=0)
    sha256:     Mapped[str|None]  = mapped_column(String(64), nullable=True)
    is_parsed:  Mapped[bool] = mapped_column(Boolean, default=False)
    is_indexed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped["Project"] = relationship(back_populates="files")
