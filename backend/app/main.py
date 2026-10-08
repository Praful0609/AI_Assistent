"""
FastAPI application entry point.
Registers routers, CORS, lifespan events, and WebSocket endpoint.
"""
import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base

log = structlog.get_logger()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup (Alembic handles migrations in prod)."""
    log.info("startup", env=settings.app_env)
    Base.metadata.create_all(bind=engine)
    yield
    log.info("shutdown")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Code Intelligence Platform",
    description="AI-powered source code understanding, documentation, and chat.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

from app.routers import projects, graph, search, chat, docs, analysis, health  # noqa: E402

app.include_router(health.router,    prefix="/api/v1")
app.include_router(projects.router,  prefix="/api/v1")
app.include_router(graph.router,     prefix="/api/v1")
app.include_router(search.router,    prefix="/api/v1")
app.include_router(chat.router,      prefix="/api/v1")
app.include_router(docs.router,      prefix="/api/v1")
app.include_router(analysis.router,  prefix="/api/v1")


# ── WebSocket — Real-time progress ────────────────────────────────────────────

class ConnectionManager:
    """Simple in-process WebSocket connection manager.
    
    NOTE: For multi-instance deployment, replace with Redis pub/sub.
    """
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}  # project_id -> [ws, ...]

    async def connect(self, project_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(project_id, []).append(ws)

    def disconnect(self, project_id: str, ws: WebSocket):
        if project_id in self.active:
            try:
                self.active[project_id].remove(ws)
            except ValueError:
                pass

    async def broadcast(self, project_id: str, data: dict):
        dead = []
        for ws in list(self.active.get(project_id, [])):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(project_id, ws)


manager = ConnectionManager()


@app.websocket("/ws/projects/{project_id}/status")
async def project_status_ws(project_id: str, websocket: WebSocket):
    """WebSocket endpoint for real-time analysis progress updates."""
    await manager.connect(project_id, websocket)
    try:
        while True:
            # Keep connection alive; server pushes updates via manager.broadcast()
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(project_id, websocket)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
def root_health():
    return {"status": "ok", "version": "0.1.0"}
