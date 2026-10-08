"""
Full analysis pipeline as a Celery task chain.

Steps:
  1. clone_or_prepare   – clone git URL or validate extracted zip dir
  2. detect_languages   – walk files, detect language per file
  3. run_ast_parser     – Tree-sitter parse per language
  4. run_static_analysis– call graph, dead code, coupling
  5. build_neo4j_graph  – write nodes/edges to Neo4j
  6. index_to_qdrant    – embed + store vectors
  7. generate_docs      – LLM doc generation
  8. mark_complete      – update DB status
"""
import structlog
from datetime import datetime, UTC
from celery import shared_task

from app.tasks.celery_app import celery_app
from app.database import SessionLocal
from app.models import Project, AnalysisRun, SourceFile, ProjectStatus, Language

log = structlog.get_logger()


def _get_session():
    return SessionLocal()


def _update_run(run_id: str, status: str, progress: int, meta: dict | None = None, error: str | None = None):
    with _get_session() as db:
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if run:
            run.status = status
            run.progress = progress
            if meta:
                run.meta = meta
            if error:
                run.error = error
            if status in ("complete", "failed"):
                run.completed_at = datetime.now(UTC)
            db.commit()


def _update_project_status(project_id: str, status: ProjectStatus):
    with _get_session() as db:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = status
            db.commit()


@celery_app.task(name="app.tasks.pipeline.run_full_pipeline", bind=True, max_retries=2)
def run_full_pipeline(
    self,
    project_id: str,
    run_id: str,
    source_type: str,
    source_value: str,
    project_dir: str,
):
    """
    Orchestrates the full analysis pipeline.
    Each step updates progress and project status in PostgreSQL.
    """
    log.info("pipeline.start", project_id=project_id, run_id=run_id)

    try:
        # ── Step 1: Clone / Prepare ───────────────────────────────────────────
        _update_run(run_id, "running", 5, {"step": "cloning"})
        _update_project_status(project_id, ProjectStatus.PARSING)

        from parsers.language_detector import clone_or_prepare
        source_dir = clone_or_prepare(source_type, source_value, project_dir)
        log.info("pipeline.cloned", source_dir=source_dir)

        # ── Step 2: Language Detection ────────────────────────────────────────
        _update_run(run_id, "running", 15, {"step": "detecting_languages"})

        from parsers.language_detector import detect_languages
        file_map = detect_languages(source_dir)  # {rel_path: Language}
        log.info("pipeline.languages_detected", file_count=len(file_map))

        # Persist file records
        with _get_session() as db:
            for rel_path, lang in file_map.items():
                import os
                abs_path = os.path.join(source_dir, rel_path)
                size = os.path.getsize(abs_path) if os.path.exists(abs_path) else 0
                sf = SourceFile(
                    project_id=project_id,
                    path=rel_path,
                    language=lang,
                    size_bytes=size,
                )
                db.add(sf)
            db.commit()

        # ── Step 3: AST Parsing ───────────────────────────────────────────────
        _update_run(run_id, "running", 30, {"step": "parsing_ast"})

        from parsers.ast_parser import parse_project
        semantic_ir = parse_project(source_dir, file_map)
        log.info("pipeline.ast_parsed", files_parsed=len(semantic_ir))

        # ── Step 4: Static Analysis ───────────────────────────────────────────
        _update_run(run_id, "running", 50, {"step": "static_analysis"})
        _update_project_status(project_id, ProjectStatus.ANALYZING)

        from parsers.static_analysis import run_analysis
        analysis_result = run_analysis(semantic_ir)
        log.info("pipeline.analysis_done")

        # ── Step 5: Neo4j Graph ───────────────────────────────────────────────
        _update_run(run_id, "running", 65, {"step": "building_graph"})

        from graph.neo4j_builder import build_graph
        build_graph(project_id, semantic_ir, analysis_result)
        log.info("pipeline.graph_built")

        # ── Step 6: Qdrant Indexing ───────────────────────────────────────────
        _update_run(run_id, "running", 80, {"step": "indexing_vectors"})
        _update_project_status(project_id, ProjectStatus.INDEXING)

        from vector.indexer import index_project
        index_project(project_id, semantic_ir)
        log.info("pipeline.indexed")

        # ── Step 7: Documentation Generation ─────────────────────────────────
        _update_run(run_id, "running", 90, {"step": "generating_docs"})

        from ai.doc_generator import generate_project_docs
        generate_project_docs(project_id, semantic_ir, analysis_result)
        log.info("pipeline.docs_generated")

        # ── Step 8: Mark Complete ─────────────────────────────────────────────
        _update_run(run_id, "complete", 100, {"step": "done"})
        _update_project_status(project_id, ProjectStatus.COMPLETE)

        # Update total file/line counts
        with _get_session() as db:
            total_files = db.query(SourceFile).filter(SourceFile.project_id == project_id).count()
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.total_files = total_files
                db.commit()

        log.info("pipeline.complete", project_id=project_id)

    except Exception as exc:
        log.error("pipeline.failed", project_id=project_id, error=str(exc))
        _update_run(run_id, "failed", 0, error=str(exc))
        _update_project_status(project_id, ProjectStatus.FAILED)
        raise self.retry(exc=exc, countdown=10)
