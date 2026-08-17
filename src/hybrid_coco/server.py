"""MCP server for hybrid-coco — exposes index via stdio."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from mcp.server import MCPServer

from .config import get_index_path
from .filters import DEFAULT_QUERY_LIMIT
from .formatters import (
    OutputStyle,
    format_file_context,
    format_file_context_missing,
    format_search,
    format_status,
    format_structure,
    format_symbol,
)
from .query import (
    IndexNotFoundError,
    file_context,
    fts_search,
    lookup_symbol,
    open_store,
    project_stats,
    structure_search,
)
from .snippet import SnippetError, read_snippet
from .store import Store
from .structure import StructureError


def _require_store(root: Path):
    try:
        return open_store(root)
    except IndexNotFoundError:
        print("No index found. Run: hc index .", file=sys.stderr)
        sys.exit(1)


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
            results = fts_search(
                store, query, path=path, languages=lang, offset=offset, limit=limit
            )
            return format_search(query, results, style=OutputStyle.MCP)
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
            results = lookup_symbol(
                store, name, path=path, languages=lang, offset=offset, limit=limit
            )
            return format_symbol(name, results, style=OutputStyle.MCP)
        except (ValueError, TypeError) as exc:
            return f"Error: {exc}"

    @server.tool(
        name="hc_file_context",
        description="All symbols in a specific file (path relative to project root).",
    )
    async def hc_file_context(path: str) -> str:
        data = file_context(store, path)
        if data is None:
            return format_file_context_missing(path)
        return format_file_context(path, data, style=OutputStyle.MCP)

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
            results = structure_search(
                root,
                store,
                kind,
                path=path,
                languages=lang,
                offset=offset,
                limit=limit,
            )
            return format_structure(kind, results, style=OutputStyle.MCP)
        except (StructureError, ValueError, TypeError) as exc:
            return f"Error: {exc}"

    @server.tool(
        name="hc_status",
        description="Index status: file count, symbol count, last update.",
    )
    async def hc_status() -> str:
        stats = project_stats(store)
        return format_status(stats, db)

    return server, store


def run_server(root: Path) -> None:
    """Start MCP stdio server for the index at root."""
    server, store = build_server(root)
    try:
        server.run(transport="stdio")
    finally:
        store.close()
