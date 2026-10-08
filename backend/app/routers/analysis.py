"""Static analysis results router."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/projects/{project_id}/analysis", tags=["analysis"])

# Populated by the pipeline task after static analysis completes
_analysis_cache: dict[str, dict] = {}


class AnalysisResponse(BaseModel):
    dead_code: list[dict]        # unused functions/classes
    circular_deps: list[list[str]]
    coupling_metrics: list[dict]
    design_patterns: list[dict]
    call_graph_summary: dict


@router.get("", response_model=AnalysisResponse)
def get_analysis(project_id: str):
    """Return static analysis results: dead code, patterns, coupling, etc."""
    if project_id not in _analysis_cache:
        raise HTTPException(status_code=404, detail="Analysis not yet complete")
    return _analysis_cache[project_id]
