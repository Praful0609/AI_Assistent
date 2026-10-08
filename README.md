# Code Intelligence Platform

AI-powered source code understanding, documentation generation, and developer chatbot using GraphRAG.

## Quick Start

### Prerequisites
- Docker Desktop (v24+)
- Git

### 1. Clone & configure
```bash
git clone <this-repo>
cd AI_Assistent
cp .env.example .env
# Edit .env — set your GEMINI_API_KEY
```

### 2. Start all services
```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend (Next.js) | http://localhost:3000 |
| Backend API + Docs | http://localhost:8000/docs |
| Neo4j Browser | http://localhost:7474 |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| Celery Flower | http://localhost:5555 |

### 3. Upload a project
1. Open http://localhost:3000
2. Click **New Project**
3. Paste a public Git URL or upload a ZIP
4. Watch the analysis progress in real-time

## Architecture

```
Upload (Git / ZIP)
      │
      ▼
Language Detection (extension + shebang)
      │
      ▼
Tree-sitter AST Parser (Python / JS / TS / Java)
      │
      ▼
Static Analysis (call graph, dead code, coupling, patterns)
      │
      ▼
Knowledge Graph Builder
      │
 ┌────┴─────┐
 ▼          ▼
Neo4j    Qdrant (bge-large embeddings)
      │
      ▼
Gemini + GraphRAG
      │
      ▼
Docs • Chat • Diagrams
```

## Project Structure

```
AI_Assistent/
├── backend/          # FastAPI + Celery workers
│   └── app/
│       ├── main.py       # FastAPI entry
│       ├── config.py     # pydantic-settings
│       ├── models/       # SQLAlchemy ORM
│       ├── routers/      # API endpoints
│       └── tasks/        # Celery pipeline
├── parsers/          # AST & language detection
│   └── languages/    # Per-language extractors
├── graph/            # Neo4j builder
├── vector/           # Qdrant embeddings
├── ai/               # GraphRAG + Gemini
├── frontend/         # Next.js 15 app
└── docker-compose.yml
```

## Development

### Backend only (no Docker)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
# In another terminal:
celery -A app.tasks.celery_app worker --loglevel=info
```

### Frontend only
```bash
cd frontend
npm install
npm run dev
```

## Scaling for Multi-user (Future)
- Add JWT auth: `owner_id` field is already on the `Project` model, just set nullable=False
- Replace in-process WebSocket manager with Redis pub/sub
- Add Qdrant collection namespacing per user (already done via `project_id`)
- Deploy with Kubernetes or Cloud Run (all services are containerized)
