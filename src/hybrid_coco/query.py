"""Query orchestration shared by CLI, MCP, and hooks."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .config import get_index_path
from .filters import (
    DEFAULT_QUERY_LIMIT,
    validate_languages,
    validate_paging,
    validate_path_filter,
)
from .store import Store
from .structure import StructureMatch, search_structure, validate_structure_kind


class IndexNotFoundError(FileNotFoundError):
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        super().__init__(str(db_path))


def open_store(root: Path) -> Store:
    db = get_index_path(root)
    if not db.exists():
        raise IndexNotFoundError(db)
    return Store(db)


def normalize_lang(lang: Union[str, list[str], None]) -> tuple[str, ...]:
    if lang is None:
        return ()
    if isinstance(lang, str):
        return validate_languages((lang,))
    if isinstance(lang, list):
        return validate_languages(tuple(str(x) for x in lang))
    raise ValueError("lang must be a string or array of strings")


def parse_query_filters(
    *,
    path: Optional[str],
    lang: Union[str, list[str], tuple[str, ...], None],
    offset: int,
    limit: int,
) -> tuple[Optional[str], tuple[str, ...], int, int]:
    path_f = validate_path_filter(path)
    if isinstance(lang, tuple):
        langs = validate_languages(lang)
    else:
        langs = normalize_lang(lang)
    validate_paging(offset=offset, limit=limit)
    return path_f, langs, offset, limit


def fts_search(
    store: Store,
    query: str,
    *,
    path: Optional[str] = None,
    languages: Union[str, list[str], tuple[str, ...], None] = None,
    offset: int = 0,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> list[dict]:
    path_f, langs, offset_v, limit_v = parse_query_filters(
        path=path, lang=languages, offset=offset, limit=limit
    )
    return store.fts_search(
        query, path=path_f, languages=langs, offset=offset_v, limit=limit_v
    )


def lookup_symbol(
    store: Store,
    name: str,
    *,
    path: Optional[str] = None,
    languages: Union[str, list[str], tuple[str, ...], None] = None,
    offset: int = 0,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> list[dict]:
    path_f, langs, offset_v, limit_v = parse_query_filters(
        path=path, lang=languages, offset=offset, limit=limit
    )
    return store.lookup_symbol(
        name, path=path_f, languages=langs, offset=offset_v, limit=limit_v
    )


def file_context(store: Store, path: str) -> dict | None:
    return store.file_context(path)


def project_stats(store: Store) -> dict:
    return store.stats()


def structure_search(
    root: Path,
    store: Store,
    kind: str,
    *,
    path: Optional[str] = None,
    languages: Union[str, list[str], tuple[str, ...], None] = None,
    offset: int = 0,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> list[StructureMatch]:
    path_f, langs, offset_v, limit_v = parse_query_filters(
        path=path, lang=languages, offset=offset, limit=limit
    )
    return search_structure(
        root,
        store,
        kind,
        path=path_f,
        languages=langs,
        offset=offset_v,
        limit=limit_v,
    )


def validate_structure_kind_param(kind: str) -> str:
    return validate_structure_kind(kind)
