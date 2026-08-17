"""Shared output formatters for CLI, MCP, and hook surfaces."""

from __future__ import annotations

import datetime
from enum import Enum
from pathlib import Path
from typing import Sequence

from .structure import StructureMatch

KIND_ORDER = ("class", "function", "method", "import")

KIND_PLURAL = {
    "class": "Classes",
    "function": "Functions",
    "method": "Methods",
    "import": "Imports",
}

STATUS_KIND_PLURAL = {"class": "classes"}


class OutputStyle(str, Enum):
    CLI = "cli"
    MCP = "mcp"
    HOOK = "hook"


def format_search(query: str, results: list[dict], *, style: OutputStyle) -> str:
    if style is OutputStyle.MCP:
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

    lines: list[str] = []
    if style is OutputStyle.HOOK:
        lines.extend([f'Search results for "{query}":', ""])
    for r in results:
        doc_part = f" — {r['docstring'][:80]}" if r.get("docstring") else ""
        lines.append(f"[{r['path']}:{r['line_start']}]  {r['kind']} {r['name']}{doc_part}")
    return "\n".join(lines)


def format_symbol(name: str, results: list[dict], *, style: OutputStyle) -> str:
    if not results:
        return f"Symbol '{name}' not found."
    lines: list[str] = []
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


def _ordered_kinds(by_kind: dict[str, list[dict]], *, style: OutputStyle) -> list[str]:
    if style is OutputStyle.HOOK:
        return [k for k in KIND_PLURAL if k in by_kind]
    seen: set[str] = set()
    ordered: list[str] = []
    for k in KIND_ORDER:
        if k in by_kind:
            ordered.append(k)
            seen.add(k)
    for k in sorted(by_kind.keys()):
        if k not in seen:
            ordered.append(k)
    return ordered


def format_file_context(path: str, data: dict, *, style: OutputStyle) -> str:
    symbols = data["symbols"]
    lang = data["language"] or "unknown"
    lines = [f"File: {path} ({lang}) — {len(symbols)} symbols", ""]

    by_kind: dict[str, list[dict]] = {}
    for sym in symbols:
        by_kind.setdefault(sym["kind"], []).append(sym)

    for kind in _ordered_kinds(by_kind, style=style):
        group = by_kind[kind]
        label = KIND_PLURAL.get(kind, kind.capitalize() + "s")
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


def format_file_context_missing(path: str) -> str:
    return f"File '{path}' not found in index."


def format_structure(kind: str, results: Sequence[StructureMatch], *, style: OutputStyle) -> str:
    if style is OutputStyle.MCP:
        if not results:
            return f"# hc_structure({kind!r})\nNo results."
        lines = [f"# hc_structure({kind!r})"]
    else:
        if not results:
            return "No results."
        lines = []
    for match in results:
        label = match.name if match.name else match.node_type
        lines.append(
            f"[{match.path}:{match.line_start}] {match.kind} {label} ({match.language})"
        )
        if match.preview:
            lines.append(f"  {match.preview}")
    return "\n".join(lines)


def format_status(stats: dict, db: Path) -> str:
    by_kind = stats["by_kind"]
    kind_parts = ", ".join(
        f"{n} {STATUS_KIND_PLURAL.get(k, k + 's')}"
        for k, n in sorted(by_kind.items(), key=lambda x: -x[1])
    )
    ts = stats["last_indexed"]
    updated = (
        datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        if ts
        else "never"
    )
    return (
        f"Index: {db}\n"
        f"Files:   {stats['files']} indexed\n"
        f"Symbols: {stats['symbols']} ({kind_parts})\n"
        f"Updated: {updated}"
    )
