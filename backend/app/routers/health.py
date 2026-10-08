"""Health check router."""
from fastapi import APIRouter
from app.database import engine
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Verify DB connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "up" if db_ok else "down",
    }
