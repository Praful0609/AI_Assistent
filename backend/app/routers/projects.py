"""
Project upload & management API router.
Handles: Git URL clone, ZIP file upload, project status, file listing.
"""
import os
import shutil
import zipfile
import tempfile
from datetime import datetime, UTC
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Project, AnalysisRun, SourceFile, SourceType, ProjectStatus
from app.schemas.project import (
    ProjectCreate, ProjectResponse, ProjectListResponse,
    AnalysisRunResponse, FileListResponse, SourceFileResponse, UploadResponse,
)
from app.tasks.celery_app import celery_app

router = APIRouter(prefix="/projects", tags=["projects"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_project_dir(project_id: str) -> Path:
    path = Path(settings.upload_dir) / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _create_analysis_run(db: Session, project_id: str) -> AnalysisRun:
    run = AnalysisRun(
        project_id=project_id,
        status="pending",
        started_at=datetime.now(UTC),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload/git", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
def upload_git_url(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
):
    """Clone a public Git repository and start analysis."""
    project = Project(
        name=payload.name,
        description=payload.description,
        source_type=SourceType.GIT_URL,
        source_url=payload.git_url,
        status=ProjectStatus.PENDING,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    project_dir = _create_project_dir(project.id)
    run = _create_analysis_run(db, project.id)

    # Dispatch Celery task
    task = celery_app.send_task(
        "app.tasks.pipeline.run_full_pipeline",
        kwargs={
            "project_id": project.id,
            "run_id": run.id,
            "source_type": "git_url",
            "source_value": payload.git_url,
            "project_dir": str(project_dir),
        },
    )

    # Store celery task ID for status tracking
    run.celery_task_id = task.id
    db.commit()

    return UploadResponse(project_id=project.id, analysis_run_id=run.id)


@router.post("/upload/zip", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_zip(
    name: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a ZIP archive of a project and start analysis."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted")

    # Check size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {settings.max_upload_size_mb} MB.",
        )

    project = Project(
        name=name,
        description=description,
        source_type=SourceType.ZIP,
        status=ProjectStatus.PENDING,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # Save zip and extract
    project_dir = _create_project_dir(project.id)
    zip_path = project_dir / "source.zip"
    zip_path.write_bytes(content)

    extract_dir = project_dir / "src"
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    project.upload_path = str(extract_dir)
    db.commit()

    run = _create_analysis_run(db, project.id)

    task = celery_app.send_task(
        "app.tasks.pipeline.run_full_pipeline",
        kwargs={
            "project_id": project.id,
            "run_id": run.id,
            "source_type": "zip",
            "source_value": str(extract_dir),
            "project_dir": str(project_dir),
        },
    )
    run.celery_task_id = task.id
    db.commit()

    return UploadResponse(project_id=project.id, analysis_run_id=run.id)


@router.get("", response_model=ProjectListResponse)
def list_projects(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """List all projects (single-user MVP — no owner filter)."""
    total = db.query(Project).count()
    projects = db.query(Project).order_by(Project.created_at.desc()).offset(skip).limit(limit).all()
    return ProjectListResponse(projects=projects, total=total)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    """Get project metadata and current status."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/runs", response_model=list[AnalysisRunResponse])
def get_analysis_runs(project_id: str, db: Session = Depends(get_db)):
    """Get all analysis runs for a project."""
    runs = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.project_id == project_id)
        .order_by(AnalysisRun.created_at.desc())
        .all()
    )
    return runs


@router.get("/{project_id}/files", response_model=FileListResponse)
def list_project_files(
    project_id: str,
    language: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List source files parsed from the project."""
    query = db.query(SourceFile).filter(SourceFile.project_id == project_id)
    if language:
        query = query.filter(SourceFile.language == language)

    total = query.count()
    files = query.offset(skip).limit(limit).all()

    # Language breakdown
    from sqlalchemy import func
    lang_counts = (
        db.query(SourceFile.language, func.count(SourceFile.id))
        .filter(SourceFile.project_id == project_id)
        .group_by(SourceFile.language)
        .all()
    )
    languages = {lang.value: count for lang, count in lang_counts}

    return FileListResponse(files=files, total=total, languages=languages)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Delete a project and all its data."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Clean up uploaded files
    project_dir = Path(settings.upload_dir) / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)

    db.delete(project)
    db.commit()
