"""
Vector embedder using sentence-transformers.
Singleton model load to avoid reloading per task.
"""
import numpy as np
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from app.config import settings


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns a list of floats."""
    model = _load_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Batch-embed a list of strings. Returns list of float vectors."""
    model = _load_model()
    vecs = model.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    return vecs.tolist()
