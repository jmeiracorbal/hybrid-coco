"""MCP server for hybrid-coco — exposes index via stdio."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from .config import get_index_path
from .store import Store


def _require_store(root: Path) -> Store:
    db = get_index_path(root)
    if not db.exists():
        print(f"No index found. Run: hc index .", file=sys.stderr)
        sys.exit(1)
    return Store(db)


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

    PLURAL = {"class": "Classes", "function": "Functions", "method": "Methods",
               "import": "Imports"}
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
    langs = ", ".join(sorted(by_kind.keys())) or "none"
    return (
        f"Index: {db}\n"
        f"Files:   {stats['files']} indexed\n"
        f"Symbols: {stats['symbols']} ({kind_parts})\n"
        f"Updated: {updated}"
    )


# ── Server factory ────────────────────────────────────────────────────────────

def build_server(root: Path) -> tuple[Server, Store]:
    store = _require_store(root)
    db = get_index_path(root)
    server = Server("hybrid-coco")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="hc_search",
                description="FTS5 search over symbol names, signatures and docstrings.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results", "default": 20},
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="hc_symbol",
                description="Exact (then prefix) symbol lookup by name.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Symbol name"},
                    },
                    "required": ["name"],
                },
            ),
            types.Tool(
                name="hc_file_context",
                description="All symbols in a specific file (path relative to project root).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative file path"},
                    },
                    "required": ["path"],
                },
            ),
            types.Tool(
                name="hc_status",
                description="Index status: file count, symbol count, last update.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        if name == "hc_search":
            query = arguments["query"]
            limit = int(arguments.get("limit", 20))
            results = store.fts_search(query, limit=limit)
            text = _fmt_search(query, results)

        elif name == "hc_symbol":
            sym_name = arguments["name"]
            results = store.lookup_symbol(sym_name)
            text = _fmt_symbol(sym_name, results)

        elif name == "hc_file_context":
            path = arguments["path"]
            data = store.file_context(path)
            text = _fmt_file_context(path, data)

        elif name == "hc_status":
            stats = store.stats()
            text = _fmt_status(stats, db)

        else:
            text = f"Unknown tool: {name}"

        return [types.TextContent(type="text", text=text)]

    return server, store


def run_server(root: Path) -> None:
    """Start MCP stdio server for the index at root."""
    import asyncio

    server, store = build_server(root)

    async def _run():
        try:
            async with stdio_server() as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
        finally:
            store.close()

    asyncio.run(_run())
