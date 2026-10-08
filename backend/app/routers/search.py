"""Semantic code search using Qdrant."""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from vector.embedder import embed_text
from qdrant_client import QdrantClient
from app.config import settings

router = APIRouter(prefix="/projects/{project_id}/search", tags=["search"])

_client: QdrantClient | None = None

def get_qdrant() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    return _client


class SearchResult(BaseModel):
    id: str
    score: float
    type: str          # function | class | file
    name: str
    file_path: str
    language: str
    snippet: str


@router.get("", response_model=list[SearchResult])
def semantic_search(
    project_id: str,
    q: str = Query(..., description="Natural language or code search query"),
    top_k: int = Query(default=10, le=50),
    language: str | None = Query(default=None),
):
    """Vector similarity search over code embeddings."""
    query_vec = embed_text(q)
    client = get_qdrant()

    filter_cond = {"must": [{"key": "project_id", "match": {"value": project_id}}]}
    if language:
        filter_cond["must"].append({"key": "language", "match": {"value": language}})

    results = client.search(
        collection_name=f"code_chunks_{project_id}",
        query_vector=query_vec,
        query_filter=filter_cond,
        limit=top_k,
        with_payload=True,
    )

    return [
        SearchResult(
            id=str(r.id),
            score=r.score,
            type=r.payload.get("type", "unknown"),
            name=r.payload.get("name", ""),
            file_path=r.payload.get("file_path", ""),
            language=r.payload.get("language", ""),
            snippet=r.payload.get("text", "")[:500],
        )
        for r in results
    ]
