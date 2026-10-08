"""
GraphRAG pipeline: combines Qdrant vector search + Neo4j graph traversal
to assemble rich context for the Gemini LLM.
"""
import structlog
from vector.embedder import embed_text
from qdrant_client import QdrantClient
from graph.neo4j_builder import get_driver
from ai.llm_backends import GeminiBackend
from ai.context_assembler import assemble_context
from ai.prompts import CHAT_SYSTEM_PROMPT
from app.config import settings

log = structlog.get_logger()

_qdrant: QdrantClient | None = None


def _get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    return _qdrant


async def query_graphrag(
    project_id: str,
    question: str,
    history: list[tuple[str, str]] = [],
    top_k: int = 8,
) -> dict:
    """
    Full GraphRAG retrieval:
    1. Embed question → Qdrant top-k chunks
    2. Extract entity names from chunks
    3. Neo4j: fetch subgraph around those entities
    4. Assemble context → Gemini prompt
    5. Return answer + sources + graph_context
    """
    # ── Step 1: Vector search ────────────────────────────────────────────────
    q_vec = embed_text(question)
    collection = f"code_chunks_{project_id.replace('-', '_')}"

    results = _get_qdrant().search(
        collection_name=collection,
        query_vector=q_vec,
        query_filter={"must": [{"key": "project_id", "match": {"value": project_id}}]},
        limit=top_k,
        with_payload=True,
    )
    chunks = [r.payload for r in results]
    log.info("graphrag.qdrant_results", count=len(chunks))

    # ── Step 2: Graph expansion ──────────────────────────────────────────────
    entity_names = list({c.get("name", "") for c in chunks if c.get("name")})
    graph_context = _expand_graph(project_id, entity_names)
    log.info("graphrag.graph_expanded", nodes=len(graph_context))

    # ── Step 3: Assemble context ─────────────────────────────────────────────
    context_text = assemble_context(question, chunks, graph_context)

    # ── Step 4: LLM call ─────────────────────────────────────────────────────
    llm = GeminiBackend()
    messages = [{"role": "user", "content": context_text}]
    answer = await llm.chat_async(messages, system=CHAT_SYSTEM_PROMPT)

    return {
        "answer": answer,
        "sources": [
            {
                "name": c.get("name"),
                "file": c.get("file_path"),
                "type": c.get("type"),
                "language": c.get("language"),
                "snippet": c.get("text", "")[:300],
            }
            for c in chunks
        ],
        "graph_context": graph_context[:20],  # limit for UI
    }


def _expand_graph(project_id: str, entity_names: list[str]) -> list[dict]:
    """Fetch 1-hop neighbours from Neo4j for given entity names."""
    if not entity_names:
        return []
    driver = get_driver()
    with driver.session() as session:
        result = session.run("""
            MATCH (n)
            WHERE n.project_id = $pid AND n.name IN $names
            OPTIONAL MATCH (n)-[r]-(neighbour)
            WHERE neighbour.project_id = $pid
            RETURN
                n.name AS entity,
                n.qualified_name AS qn,
                labels(n)[0] AS type,
                collect({
                    name: neighbour.name,
                    type: labels(neighbour)[0],
                    rel: type(r)
                }) AS neighbours
            LIMIT 50
        """, pid=project_id, names=entity_names)
        return [dict(r) for r in result]
