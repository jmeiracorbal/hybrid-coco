"""MCP server for hybrid-coco — exposes index via stdio."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from typing import Optional, Union

from mcp.server import MCPServer

from .config import get_index_path
from .filters import (
    DEFAULT_QUERY_LIMIT,
    validate_languages,
    validate_paging,
    validate_path_filter,
)
from .embedder import embed_texts
from .snippet import SnippetError, read_snippet
from .store import Store
from .structure import StructureError, search_structure
from .vectors import VectorError, semantic_search


def _require_store(root: Path) -> Store:
    db = get_index_path(root)
    if not db.exists():
        print("No index found. Run: hc index .", file=sys.stderr)
        sys.exit(1)
    return Store(db)


def _normalize_lang(lang: Union[str, list[str], None]) -> tuple[str, ...]:
    if lang is None:
        return ()
    if isinstance(lang, str):
        return validate_languages((lang,))
    if isinstance(lang, list):
        return validate_languages(tuple(str(x) for x in lang))
    raise ValueError("lang must be a string or array of strings")


def _parse_filters(
    *,
    path: Optional[str],
    lang: Union[str, list[str], None],
    offset: int,
    limit: int,
) -> tuple[Optional[str], tuple[str, ...], int, int]:
    path_f = validate_path_filter(path)
    langs = _normalize_lang(lang)
    validate_paging(offset=offset, limit=limit)
    return path_f, langs, offset, limit


# ── Response formatters ───────────────────────────────────────────────────────

def _fmt_search(query: str, results: list[dict]) -> str:
    if not results:
        return f"# hc_search({query!r})\nNo results."
    lines = [f"# hc_search({query!r})"]
    for r in results:
        lines.append(f"[{r['path']}:{r['line_start']}] {r['kind']} {r['name']}")
        if r.get("signature"):
            lines.append(f"  sig: {r['signature']}")
        if r.get("docstring"):
            snippet = r["docstring"][:120].replace("\n", " ")
            lines.append(f"  doc: {snippet}")
    return "\n".join(lines)


def _fmt_symbol(name: str, results: list[dict]) -> str:
    if not results:
        return f"Symbol '{name}' not found."
    lines = []
    for r in results:
        parent = f" (in {r['parent_name']})" if r.get("parent_name") else ""
        lines.append(
            f"{r['kind']} {r['name']}{parent} @ {r['path']}:{r['line_start']}-{r['line_end']}"
        )
        if r.get("signature"):
            lines.append(f"  sig: {r['signature']}")
        if r.get("docstring"):
            snippet = r["docstring"][:120].replace("\n", " ")
            lines.append(f"  doc: {snippet}")
    return "\n".join(lines)


def _fmt_file_context(path: str, data: dict | None) -> str:
    if data is None:
        return f"File '{path}' not found in index."
    symbols = data["symbols"]
    lang = data["language"] or "unknown"
    lines = [f"File: {path} ({lang}) — {len(symbols)} symbols", ""]

    by_kind: dict[str, list[dict]] = {}
    for sym in symbols:
        by_kind.setdefault(sym["kind"], []).append(sym)

    KIND_ORDER = ["class", "function", "method", "import"]
    seen = set()
    ordered_kinds = []
    for k in KIND_ORDER:
        if k in by_kind:
            ordered_kinds.append(k)
            seen.add(k)
    for k in sorted(by_kind.keys()):
        if k not in seen:
            ordered_kinds.append(k)

    PLURAL = {
        "class": "Classes",
        "function": "Functions",
        "method": "Methods",
        "import": "Imports",
    }
    for kind in ordered_kinds:
        group = by_kind[kind]
        label = PLURAL.get(kind, kind.capitalize() + "s")
        lines.append(f"{label} ({len(group)}):")
        for sym in group:
            if kind == "import":
                lines.append(f"  {sym['name']}")
            elif sym.get("signature"):
                lines.append(f"  {sym['name']} @ {sym['line_start']}  {sym['signature']}")
            else:
                lines.append(f"  {sym['name']} @ {sym['line_start']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _fmt_structure(kind: str, results: list) -> str:
    if not results:
        return f"# hc_structure({kind!r})\nNo results."
    lines = [f"# hc_structure({kind!r})"]
    for match in results:
        label = match.name if match.name else match.node_type
        lines.append(
            f"[{match.path}:{match.line_start}] {match.kind} {label} ({match.language})"
        )
        if match.preview:
            lines.append(f"  {match.preview}")
    return "\n".join(lines)


def _fmt_semantic(query: str, results: list[dict]) -> str:
    if not results:
        return f"# hc_semantic({query!r})\nNo results."
    lines = [f"# hc_semantic({query!r})"]
    for r in results:
        lines.append(
            f"[{r['path']}:{r['line_start']}] {r['kind']} {r['name']}  "
            f"dist={r['distance']:.4f}"
        )
        if r.get("signature"):
            lines.append(f"  sig: {r['signature']}")
        if r.get("docstring"):
            snippet = r["docstring"][:120].replace("\n", " ")
            lines.append(f"  doc: {snippet}")
    return "\n".join(lines)


def _fmt_status(stats: dict, db: Path) -> str:
    by_kind = stats["by_kind"]
    PLURAL = {"class": "classes"}
    kind_parts = ", ".join(
        f"{n} {PLURAL.get(k, k + 's')}"
        for k, n in sorted(by_kind.items(), key=lambda x: -x[1])
    )
    ts = stats["last_indexed"]
    updated = (
        datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        if ts else "never"
    )
    return (
        f"Index: {db}\n"
        f"Files:   {stats['files']} indexed\n"
        f"Symbols: {stats['symbols']} ({kind_parts})\n"
        f"Updated: {updated}"
    )


# ── Server factory ────────────────────────────────────────────────────────────

def build_server(root: Path) -> tuple[MCPServer, Store]:
    store = _require_store(root)
    db = get_index_path(root)
    server = MCPServer("hybrid-coco")

    @server.tool(
        name="hc_search",
        description=(
            "FTS5 search over symbol names, signatures and docstrings. "
            "Optional path/lang filters AND together; use offset/limit to page."
        ),
    )
    async def hc_search(
        query: str,
        path: Optional[str] = None,
        lang: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = DEFAULT_QUERY_LIMIT,
    ) -> str:
        try:
            path_f, langs, offset_v, limit_v = _parse_filters(
                path=path, lang=lang, offset=offset, limit=limit
            )
            results = store.fts_search(
                query, path=path_f, languages=langs, offset=offset_v, limit=limit_v
            )
            return _fmt_search(query, results)
        except (ValueError, TypeError) as exc:
            return f"Error: {exc}"

    @server.tool(
        name="hc_symbol",
        description=(
            "Exact (then prefix) symbol lookup by name. "
            "Optional path/lang filters AND together; use offset/limit to page."
        ),
    )
    async def hc_symbol(
        name: str,
        path: Optional[str] = None,
        lang: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = DEFAULT_QUERY_LIMIT,
    ) -> str:
        try:
            path_f, langs, offset_v, limit_v = _parse_filters(
                path=path, lang=lang, offset=offset, limit=limit
            )
            results = store.lookup_symbol(
                name, path=path_f, languages=langs, offset=offset_v, limit=limit_v
            )
            return _fmt_symbol(name, results)
        except (ValueError, TypeError) as exc:
            return f"Error: {exc}"

    @server.tool(
        name="hc_file_context",
        description="All symbols in a specific file (path relative to project root).",
    )
    async def hc_file_context(path: str) -> str:
        data = store.file_context(path)
        return _fmt_file_context(path, data)

    @server.tool(
        name="hc_snippet",
        description=(
            "Read a bounded slice of source from disk (path relative to project root). "
            "line_start and line_end are 1-based and inclusive."
        ),
    )
    async def hc_snippet(path: str, line_start: int, line_end: int) -> str:
        try:
            return read_snippet(root, path, line_start, line_end)
        except SnippetError as exc:
            return f"Error: {exc}"

    @server.tool(
        name="hc_structure",
        description=(
            "Structural search by tree-sitter shape over indexed files. "
            "kind is one of: function, method, class, import. "
            "Optional path/lang filters AND together; use offset/limit to page."
        ),
    )
    async def hc_structure(
        kind: str,
        path: Optional[str] = None,
        lang: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = DEFAULT_QUERY_LIMIT,
    ) -> str:
        try:
            path_f, langs, offset_v, limit_v = _parse_filters(
                path=path, lang=lang, offset=offset, limit=limit
            )
            results = search_structure(
                root,
                store,
                kind,
                path=path_f,
                languages=langs,
                offset=offset_v,
                limit=limit_v,
            )
            return _fmt_structure(kind, results)
        except (StructureError, ValueError, TypeError) as exc:
            return f"Error: {exc}"

    @server.tool(
        name="hc_semantic",
        description=(
            "Nearest-neighbour search over embeddings produced by hc embed. "
            "Uses the model stored in the index. "
            "Optional path/lang filters AND together; use offset/limit to page."
        ),
    )
    async def hc_semantic(
        query: str,
        path: Optional[str] = None,
        lang: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = DEFAULT_QUERY_LIMIT,
    ) -> str:
        try:
            path_f, langs, offset_v, limit_v = _parse_filters(
                path=path, lang=lang, offset=offset, limit=limit
            )
            results = semantic_search(
                store=store,
                query=query,
                embed_texts=embed_texts,
                path=path_f,
                languages=langs,
                offset=offset_v,
                limit=limit_v,
            )
            return _fmt_semantic(query, results)
        except (VectorError, ValueError, TypeError) as exc:
            return f"Error: {exc}"

    @server.tool(
        name="hc_status",
        description="Index status: file count, symbol count, last update.",
    )
    async def hc_status() -> str:
        stats = store.stats()
        return _fmt_status(stats, db)

    return server, store


def run_server(root: Path) -> None:
    """Start MCP stdio server for the index at root."""
    server, store = build_server(root)
    try:
        server.run(transport="stdio")
    finally:
        store.close()
