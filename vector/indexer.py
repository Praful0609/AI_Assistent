"""
Qdrant indexing pipeline.
Creates a per-project collection and upserts code chunk embeddings.
"""
import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, OptimizersConfigDiff
)
from app.config import settings
from vector.chunker import chunk_semantic_ir, Chunk
from vector.embedder import embed_batch
from parsers.semantic_ir import FileIR

log = structlog.get_logger()

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key or None,
        )
    return _client


def _collection_name(project_id: str) -> str:
    return f"code_chunks_{project_id.replace('-', '_')}"


def _ensure_collection(client: QdrantClient, name: str):
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=settings.embedding_dimension,
                distance=Distance.COSINE,
            ),
            optimizers_config=OptimizersConfigDiff(indexing_threshold=10_000),
        )
        log.info("qdrant.collection_created", name=name)


def index_project(project_id: str, file_irs: list[FileIR], batch_size: int = 100):
    """
    Chunk, embed, and upsert all code chunks for a project into Qdrant.
    Idempotent: uses deterministic chunk IDs so re-runs safely upsert.
    """
    client = get_client()
    collection = _collection_name(project_id)
    _ensure_collection(client, collection)

    chunks = chunk_semantic_ir(project_id, file_irs)
    log.info("qdrant.indexing", project_id=project_id, chunks=len(chunks))

    # Batch embed + upsert
    for i in range(0, len(chunks), batch_size):
        batch: list[Chunk] = chunks[i : i + batch_size]
        texts = [c.text for c in batch]
        vectors = embed_batch(texts)

        points = [
            PointStruct(
                id=c.id,
                vector=v,
                payload={
                    "project_id": c.project_id,
                    "type": c.chunk_type,
                    "name": c.name,
                    "file_path": c.file_path,
                    "language": c.language,
                    "text": c.text,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                },
            )
            for c, v in zip(batch, vectors)
        ]
        client.upsert(collection_name=collection, points=points)
        log.info("qdrant.batch_upserted", batch=i // batch_size + 1, size=len(batch))

    log.info("qdrant.indexing_complete", project_id=project_id, total=len(chunks))
