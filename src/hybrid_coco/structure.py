"""Structural search with tree-sitter queries over indexed files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from tree_sitter import Parser, Query, QueryCursor

from .filters import (
    DEFAULT_QUERY_LIMIT,
    matches_path,
    path_filter_spec,
    validate_languages,
    validate_paging,
    validate_path_filter,
)
from .languages.registry import get_language_spec, get_structure_query, load_tree_sitter
from .parsers.ts_utils import node_text
from .store import Store

STRUCTURE_KINDS: tuple[str, ...] = ("function", "method", "class", "import")

_PARSER_CACHE: dict[str, Parser] = {}
_QUERY_CACHE: dict[tuple[str, str], Query] = {}


class StructureError(ValueError):
    """Invalid structural search request."""


@dataclass(frozen=True)
class StructureMatch:
    path: str
    language: str
    kind: str
    node_type: str
    name: Optional[str]
    line_start: int
    line_end: int
    preview: str


def validate_structure_kind(kind: str) -> str:
    normalized = kind.strip().lower()
    if normalized not in STRUCTURE_KINDS:
        allowed = ", ".join(STRUCTURE_KINDS)
        raise StructureError(f"unknown kind {kind!r}; expected one of: {allowed}")
    return normalized


def _preview(node, source: bytes) -> str:
    text = node_text(node, source)
    first = text.splitlines()[0] if text else ""
    return first[:120]


def _ancestor_types(node) -> set[str]:
    types: set[str] = set()
    current = node.parent
    while current is not None:
        types.add(current.type)
        current = current.parent
    return types


def _include_match(language: str, kind: str, node) -> bool:
    if kind == "function" and language == "python":
        return "class_definition" not in _ancestor_types(node)
    if kind == "method" and language == "python":
        return "class_definition" in _ancestor_types(node)
    return True


def _parser_for(language: str) -> Parser:
    if language not in _PARSER_CACHE:
        _PARSER_CACHE[language] = Parser(load_tree_sitter(language))
    return _PARSER_CACHE[language]


def _query_for(language: str, kind: str) -> Optional[Query]:
    query_text = get_structure_query(language, kind)
    if query_text is None:
        return None
    key = (language, kind)
    if key not in _QUERY_CACHE:
        _QUERY_CACHE[key] = Query(load_tree_sitter(language), query_text)
    return _QUERY_CACHE[key]


def _match_file(
    *,
    root: Path,
    rel_path: str,
    language: str,
    kind: str,
    source: bytes,
) -> list[StructureMatch]:
    query = _query_for(language, kind)
    if query is None:
        return []

    parser = _parser_for(language)
    tree = parser.parse(source)
    cursor = QueryCursor(query)
    matches: list[StructureMatch] = []

    for _pattern_index, captures in cursor.matches(tree.root_node):
        name_nodes = captures.get("name")
        node_nodes = captures.get("node")
        if name_nodes:
            node = name_nodes[0]
            name = node_text(node, source)
        elif node_nodes:
            node = node_nodes[0]
            name = None
        else:
            continue

        if not _include_match(language, kind, node):
            continue

        matches.append(
            StructureMatch(
                path=rel_path,
                language=language,
                kind=kind,
                node_type=node.type,
                name=name,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                preview=_preview(node, source),
            )
        )

    return matches


def search_structure(
    root: Path,
    store: Store,
    kind: str,
    *,
    path: Optional[str] = None,
    languages: Sequence[str] = (),
    offset: int = 0,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> list[StructureMatch]:
    """Run a structural query over indexed files."""
    normalized_kind = validate_structure_kind(kind)
    path_pat = validate_path_filter(path)
    langs = validate_languages(languages)
    validate_paging(offset=offset, limit=limit)

    path_spec = path_filter_spec(path_pat) if path_pat is not None else None
    lang_set = set(langs) if langs else None

    collected: list[StructureMatch] = []
    root_resolved = root.resolve()

    for row in store.all_files():
        rel_path = row["path"]
        language = row["language"]
        if language is None:
            continue
        if lang_set is not None and language.lower() not in lang_set:
            continue
        if path_spec is not None and not matches_path(rel_path, path_spec):
            continue
        if get_language_spec(language) is None:
            continue
        if get_structure_query(language, normalized_kind) is None:
            continue

        file_path = root_resolved / rel_path
        if not file_path.is_file():
            continue

        source = file_path.read_bytes()
        collected.extend(
            _match_file(
                root=root_resolved,
                rel_path=rel_path,
                language=language,
                kind=normalized_kind,
                source=source,
            )
        )

    collected.sort(key=lambda m: (m.path, m.line_start, m.name or ""))
    return collected[offset : offset + limit]
