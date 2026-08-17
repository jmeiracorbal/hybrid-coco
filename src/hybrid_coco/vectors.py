"""Optional sqlite-vec index. Loaded only from embed/semantic paths."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence

from .filters import DEFAULT_QUERY_LIMIT, validate_paging
from .store import Store

_VEC_TABLE = "vec_symbols"


class VectorError(Exception):
    """embedding / sqlite-vec failure with an explicit operator message."""


class VectorExtraMissingError(VectorError):
    def __init__(self) -> None:
        super().__init__(
            "sqlite-vec extra is not installed. Run: pip install 'hybrid-coco[vec]'"
        )


class VectorNotReadyError(VectorError):
    def __init__(self) -> None:
        super().__init__("no embeddings in the index. Run: hc embed --model <name>")


class EmbedFn(Protocol):
    def __call__(self, *, model: str, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class EmbedResult:
    model: str
    dimensions: int
    vectors: int


def extra_installed() -> bool:
    try:
        import sqlite_vec  # noqa: F401
    except ImportError:
        return False
    return True


def symbol_embed_text(sym: dict) -> str:
    parts = [str(sym["kind"]), str(sym["name"])]
    signature = sym.get("signature")
    docstring = sym.get("docstring")
    if signature:
        parts.append(str(signature))
    if docstring:
        parts.append(str(docstring))
    return "\n".join(parts)


def load_sqlite_vec(conn: sqlite3.Connection) -> None:
    try:
        import sqlite_vec
    except ImportError as exc:
        raise VectorExtraMissingError from exc
    try:
        conn.enable_load_extension(True)
    except (AttributeError, sqlite3.OperationalError) as exc:
        raise VectorError("this Python sqlite3 build cannot load extensions") from exc
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


def _parse_dimensions(value: str) -> int:
    if not value.isdigit():
        raise VectorError(f"invalid stored dimensions: {value!r}")
    dimensions = int(value)
    if dimensions < 1:
        raise VectorError("stored dimensions must be >= 1")
    return dimensions


def _vec_table_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'virtual') AND name = ?",
        (_VEC_TABLE,),
    ).fetchone()
    return row is not None


def _recreate_vec_table(conn: sqlite3.Connection, dimensions: int) -> None:
    if dimensions < 1:
        raise VectorError("embedding dimensions must be >= 1")
    conn.execute(f"DROP TABLE IF EXISTS {_VEC_TABLE}")
    conn.execute(
        f"CREATE VIRTUAL TABLE {_VEC_TABLE} USING vec0(embedding float[{dimensions}])"
    )


def _serialize(vector: list[float]) -> bytes:
    from sqlite_vec import serialize_float32

    return serialize_float32(vector)


def embed_index(*, store: Store, model: str, embed_texts: EmbedFn) -> EmbedResult:
    if not model or not model.strip():
        raise VectorError("model must be non-empty")
    model = model.strip()
    symbols = store.list_symbols_for_embed()
    if not symbols:
        raise VectorError("no symbols in index. Run: hc index")
    texts = [symbol_embed_text(sym) for sym in symbols]
    vectors = embed_texts(model=model, texts=texts)
    if len(vectors) != len(texts):
        raise VectorError("embedder returned a different number of vectors than texts")
    dimensions = len(vectors[0])
    if dimensions < 1:
        raise VectorError("embedding dimensions must be >= 1")
    for index, vector in enumerate(vectors):
        if len(vector) != dimensions:
            raise VectorError(
                f"vector {index} has dimension {len(vector)}, expected {dimensions}"
            )

    load_sqlite_vec(store.conn)
    _recreate_vec_table(store.conn, dimensions)
    rows = [
        (int(symbols[i]["id"]), _serialize(vectors[i]))
        for i in range(len(symbols))
    ]
    store.conn.executemany(
        f"INSERT INTO {_VEC_TABLE}(rowid, embedding) VALUES (?, ?)",
        rows,
    )
    store.set_vec_meta("model", model)
    store.set_vec_meta("dimensions", str(dimensions))
    store.conn.commit()
    return EmbedResult(model=model, dimensions=dimensions, vectors=len(rows))


def embedding_status(store: Store) -> EmbedResult | None:
    meta = store.vec_meta()
    if "model" not in meta or "dimensions" not in meta:
        return None
    load_sqlite_vec(store.conn)
    if not _vec_table_exists(store.conn):
        return None
    count = store.conn.execute(f"SELECT count(*) FROM {_VEC_TABLE}").fetchone()[0]
    return EmbedResult(
        model=meta["model"],
        dimensions=_parse_dimensions(meta["dimensions"]),
        vectors=int(count),
    )


def _knn(
    conn: sqlite3.Connection,
    query: list[float],
    k: int,
    rowids: Sequence[int] | None,
) -> list[tuple[int, float]]:
    blob = _serialize(query)
    if rowids is None:
        rows = conn.execute(
            f"SELECT rowid, distance FROM {_VEC_TABLE} WHERE embedding MATCH ? AND k = ?",
            (blob, k),
        ).fetchall()
    else:
        placeholders = ",".join("?" * len(rowids))
        rows = conn.execute(
            f"""SELECT rowid, distance FROM {_VEC_TABLE}
                WHERE embedding MATCH ? AND k = ?
                  AND rowid IN ({placeholders})""",
            (blob, k, *rowids),
        ).fetchall()
    return [(int(row[0]), float(row[1])) for row in rows]


def semantic_search(
    *,
    store: Store,
    query: str,
    embed_texts: EmbedFn,
    path: Optional[str] = None,
    languages: Sequence[str] = (),
    offset: int = 0,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> list[dict]:
    if not query or not query.strip():
        raise VectorError("query must be non-empty")
    validate_paging(offset=offset, limit=limit)
    meta = store.vec_meta()
    if "model" not in meta or "dimensions" not in meta:
        raise VectorNotReadyError
    model = meta["model"]
    if not model:
        raise VectorError("stored embedding model is empty")
    stored_dim = _parse_dimensions(meta["dimensions"])

    load_sqlite_vec(store.conn)
    if not _vec_table_exists(store.conn):
        raise VectorNotReadyError

    query_vectors = embed_texts(model=model, texts=[query.strip()])
    if len(query_vectors) != 1:
        raise VectorError("embedder returned a different number of vectors than texts")
    query_vec = query_vectors[0]
    if len(query_vec) != stored_dim:
        raise VectorError(
            f"query vector dimension {len(query_vec)} does not match stored {stored_dim}"
        )

    k = offset + limit
    has_filters = path is not None or tuple(languages) != ()
    if has_filters:
        rowids = store.filtered_symbol_ids(path=path, languages=languages)
        if not rowids:
            return []
        ranked = _knn(store.conn, query_vec, k, rowids)
    else:
        ranked = _knn(store.conn, query_vec, k, None)

    paged = ranked[offset : offset + limit]
    by_id = store.symbols_by_ids([rowid for rowid, _ in paged])
    results: list[dict] = []
    for rowid, distance in paged:
        if rowid not in by_id:
            raise VectorError(f"embedding rowid {rowid} has no matching symbol")
        hit = dict(by_id[rowid])
        hit["distance"] = distance
        results.append(hit)
    return results
