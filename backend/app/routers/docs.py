"""Documentation retrieval and diagram generation router."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ai.diagram_generator import generate_diagram

router = APIRouter(prefix="/projects/{project_id}", tags=["docs"])

# Simple in-memory cache for generated docs (replace with DB store in prod)
_docs_cache: dict[str, dict] = {}


class DocSection(BaseModel):
    title: str
    content: str   # Markdown
    type: str      # "overview" | "module" | "api" | "readme"


class DocsResponse(BaseModel):
    sections: list[DocSection]


class DiagramResponse(BaseModel):
    type: str
    format: str    # "mermaid" | "json"
    content: str


@router.get("/docs", response_model=DocsResponse)
def get_docs(project_id: str):
    """Get generated documentation for a project."""
    if project_id not in _docs_cache:
        raise HTTPException(status_code=404, detail="Documentation not yet generated")
    return DocsResponse(sections=_docs_cache[project_id])


@router.get("/diagrams/{diagram_type}", response_model=DiagramResponse)
def get_diagram(project_id: str, diagram_type: str):
    """
    Generate/retrieve a diagram for the project.
    diagram_type: class | sequence | dependency | module
    """
    supported = {"class", "sequence", "dependency", "module"}
    if diagram_type not in supported:
        raise HTTPException(status_code=400, detail=f"Unsupported diagram type. Choose from: {supported}")

    content, fmt = generate_diagram(project_id, diagram_type)
    return DiagramResponse(type=diagram_type, format=fmt, content=content)
