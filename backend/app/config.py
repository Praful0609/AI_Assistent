"""
Application configuration via pydantic-settings.
Values are read from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


from typing import Any
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me"
    cors_origins: str | list[str] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="after")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [x.strip() for x in v.split(",") if x.strip()]
        if isinstance(v, list):
            return v
        return ["http://localhost:3000"]

    @field_validator("qdrant_api_key", mode="before")
    @classmethod
    def parse_qdrant_key(cls, v: Any) -> str | None:
        if isinstance(v, str):
            v = v.split("#")[0].strip()
            return v if v else None
        return v

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+psycopg2://codeinsight:codeinsight_dev_pass@localhost:5432/codeinsight"
    )

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── Neo4j ─────────────────────────────────────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j_dev_pass"

    # ── Qdrant ────────────────────────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None

    # ── Gemini ────────────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_dimension: int = 1024

    # ── File Storage ──────────────────────────────────────────────────────────
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 500


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — import this instead of instantiating Settings directly."""
    return Settings()


settings = get_settings()
