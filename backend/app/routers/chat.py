"""AI chat router — GraphRAG-powered Q&A over a project."""
from fastapi import APIRouter
from pydantic import BaseModel
from ai.graphrag import query_graphrag

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]   # code chunk citations
    graph_context: list[dict]  # relevant graph nodes shown in UI


@router.post("", response_model=ChatResponse)
async def chat(project_id: str, request: ChatRequest):
    """
    Answer developer questions using GraphRAG:
    1. Embed query → Qdrant vector search
    2. Expand top results via Neo4j graph
    3. Assemble context → Gemini LLM
    4. Return answer + citations
    """
    result = await query_graphrag(
        project_id=project_id,
        question=request.message,
        history=[(m.role, m.content) for m in request.history],
    )
    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        graph_context=result["graph_context"],
    )
