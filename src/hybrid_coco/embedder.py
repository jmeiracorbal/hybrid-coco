"""Production embedder. fastembed is imported only when this function runs."""

from __future__ import annotations

from .vectors import VectorError, VectorExtraMissingError


def embed_texts(*, model: str, texts: list[str]) -> list[list[float]]:
    if not model or not model.strip():
        raise VectorError("model must be non-empty")
    if not texts:
        raise VectorError("texts must be non-empty")
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise VectorExtraMissingError from exc
    embedding_model = TextEmbedding(model_name=model.strip())
    vectors: list[list[float]] = []
    for vec in embedding_model.embed(texts):
        vectors.append([float(x) for x in vec])
    if len(vectors) != len(texts):
        raise VectorError("embedder returned a different number of vectors than texts")
    return vectors
