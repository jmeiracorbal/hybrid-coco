"""CLI entry point for hybrid-coco (hc)."""

from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
import sys
from pathlib import Path

import click

from .config import get_index_path
from .indexer import index_path
from .store import Store

# ── Assets ────────────────────────────────────────────────────────────────────

_ASSETS_DIR = Path(__file__).parent / "assets"

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)


def _require_store(root: Path) -> Store:
    db = get_index_path(root)
    if not db.exists():
        click.echo(f"No index found at {db}. Run: hc index {root}", err=True)
        sys.exit(1)
    return Store(db)


# ── CLI group ─────────────────────────────────────────────────────────────────

@click.group()
@click.version_option("0.1.0", prog_name="hc")
def main():
    """hybrid-coco — local code intelligence."""


# ── hc index ─────────────────────────────────────────────────────────────────

@main.command("index")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("--exclude", multiple=True, help="Additional patterns to exclude (not yet wired)")
@click.option("--verbose", "-v", is_flag=True)
def cmd_index(path: str, exclude: tuple, verbose: bool):
    """Index PATH (default: current directory)."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    root = Path(path).resolve()
    click.echo(f"Indexing {root} …", err=True)
    result = index_path(root)
    click.echo(
        f"Done. Indexed: {result.indexed}  Skipped (unchanged): {result.skipped}  Errors: {result.errors}"
    )


# ── hc update ────────────────────────────────────────────────────────────────

@main.command("update")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("--verbose", "-v", is_flag=True)
def cmd_update(path: str, verbose: bool):
    """Re-index only changed files in PATH."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    root = Path(path).resolve()
    db = get_index_path(root)
    if not db.exists():
        click.echo(f"No index found. Run: hc index {root}", err=True)
        sys.exit(1)

    click.echo(f"Updating {root} …", err=True)
    result = index_path(root, force=False)
    click.echo(
        f"Done. Re-indexed: {result.indexed}  Unchanged: {result.skipped}  Errors: {result.errors}"
    )


# ── hc status ────────────────────────────────────────────────────────────────

@main.command("status")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
def cmd_status(path: str):
    """Show index statistics."""
    root = Path(path).resolve()
    store = _require_store(root)
    try:
        s = store.stats()
    finally:
        store.close()

    db = get_index_path(root)
    by_kind = s["by_kind"]
    PLURAL = {"class": "classes"}
    kind_parts = ", ".join(
        f"{n} {PLURAL.get(k, k + 's')}" for k, n in sorted(by_kind.items(), key=lambda x: -x[1])
    )

    ts = s["last_indexed"]
    if ts:
        updated = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    else:
        updated = "never"

    click.echo(f"Index: {db}")
    click.echo(f"Files:   {s['files']} indexed")
    click.echo(f"Symbols: {s['symbols']} ({kind_parts})")
    click.echo(f"Updated: {updated}")


# ── hc query ─────────────────────────────────────────────────────────────────

@main.command("query")
@click.argument("text")
@click.option("--limit", default=20, show_default=True)
def cmd_query(text: str, limit: int):
    """FTS5 search across symbol names, signatures and docstrings."""
    root = Path.cwd()
    store = _require_store(root)
    try:
        results = store.fts_search(text, limit=limit)
    finally:
        store.close()

    if not results:
        click.echo("No results.")
        return

    for r in results:
        doc_part = f" — {r['docstring'][:80]}" if r.get("docstring") else ""
        click.echo(f"[{r['path']}:{r['line_start']}]  {r['kind']} {r['name']}{doc_part}")


# ── hc symbol ────────────────────────────────────────────────────────────────

@main.command("symbol")
@click.argument("name")
def cmd_symbol(name: str):
    """Lookup a symbol by name (exact, then prefix)."""
    root = Path.cwd()
    store = _require_store(root)
    try:
        results = store.lookup_symbol(name)
    finally:
        store.close()

    if not results:
        click.echo(f"Symbol '{name}' not found.")
        return

    for r in results:
        parent = f" (in {r['parent_name']})" if r.get("parent_name") else ""
        click.echo(f"{r['kind']} {r['name']}{parent} @ {r['path']}:{r['line_start']}-{r['line_end']}")
        if r.get("signature"):
            click.echo(f"  sig: {r['signature']}")
        if r.get("docstring"):
            click.echo(f"  doc: {r['docstring'][:120]}")


# ── hc file-context ──────────────────────────────────────────────────────────

@main.command("file-context")
@click.argument("path")
def cmd_file_context(path: str):
    """Show all symbols in PATH (relative to project root). ~97% token savings vs cat."""
    root = Path.cwd()
    store = _require_store(root)
    try:
        data = store.file_context(path)
    finally:
        store.close()

    if data is None:
        click.echo(f"File '{path}' not found in index. Is it indexed? Run: hc update")
        sys.exit(1)

    symbols = data["symbols"]
    lang = data["language"] or "unknown"
    click.echo(f"File: {path} ({lang}) — {len(symbols)} symbols")

    by_kind: dict[str, list[dict]] = {}
    for sym in symbols:
        by_kind.setdefault(sym["kind"], []).append(sym)

    KIND_ORDER = ["class", "function", "method", "import"]
    seen: set[str] = set()
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
    click.echo()
    for kind in ordered_kinds:
        group = by_kind[kind]
        label = PLURAL.get(kind, kind.capitalize() + "s")
        click.echo(f"{label} ({len(group)}):")
        for sym in group:
            if kind == "import":
                click.echo(f"  {sym['name']}")
            elif sym.get("signature"):
                click.echo(f"  {sym['name']} @ {sym['line_start']}  {sym['signature']}")
            else:
                click.echo(f"  {sym['name']} @ {sym['line_start']}")
        click.echo()


# ── hc serve ─────────────────────────────────────────────────────────────────

@main.command("serve")
def cmd_serve():
    """Start MCP server (stdio). Register in Claude Code with: hc init"""
    from .server import run_server
    run_server(Path.cwd())


# ── hc init ──────────────────────────────────────────────────────────────────

MCP_ENTRY = {
    "command": "hc",
    "args": ["serve"],
    "type": "stdio",
}

MCP_TOOLS = ["hc_search", "hc_symbol", "hc_file_context", "hc_status"]


def _merge_mcp_settings(settings_path: Path) -> None:
    """Merge hybrid-coco MCP entry into the given settings.json (creates if missing)."""
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    data.setdefault("mcpServers", {})
    data["mcpServers"]["hybrid-coco"] = MCP_ENTRY

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


# ── Global Claude Code integration ───────────────────────────────────────────

_HC_HOOK_PATH_PRE = "~/.claude/hooks/hc-pre-tool-use.sh"
_HC_HOOK_PATH_POST = "~/.claude/hooks/hc-post-tool-use.sh"

_HC_PRE_HOOK_ENTRY = {
    "matcher": "Read|Grep",
    "hooks": [{"type": "command", "command": _HC_HOOK_PATH_PRE}],
}
_HC_POST_HOOK_ENTRY = {
    "matcher": "Write|Edit",
    "hooks": [{"type": "command", "command": _HC_HOOK_PATH_POST}],
}


def _entry_present(entries: list, command: str) -> bool:
    """Return True if any hook entry already references the given command."""
    for entry in entries:
        for hook in entry.get("hooks", []):
            if hook.get("command") == command:
                return True
    return False


def _install_global(claude_dir: Path) -> dict[str, bool]:
    """
    Install hybrid-coco awareness in Claude Code global config.

    Returns a dict with keys:
      awareness_written, claude_md_updated, hooks_installed, settings_patched
    """
    result = {
        "awareness_written": False,
        "claude_md_updated": False,
        "hooks_installed": False,
        "settings_patched": False,
    }

    # 1. Write ~/.claude/hybrid-coco.md
    src_awareness = _ASSETS_DIR / "hybrid-coco.md"
    dst_awareness = claude_dir / "hybrid-coco.md"
    dst_awareness.write_text(src_awareness.read_text(encoding="utf-8"), encoding="utf-8")
    result["awareness_written"] = True

    # 2. Add @hybrid-coco.md to ~/.claude/CLAUDE.md
    claude_md = claude_dir / "CLAUDE.md"
    tag = "@hybrid-coco.md"
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
    else:
        content = ""
    if tag not in content:
        sep = "\n" if content and not content.endswith("\n") else ""
        claude_md.write_text(content + sep + tag + "\n", encoding="utf-8")
        result["claude_md_updated"] = True
    else:
        result["claude_md_updated"] = False  # already present

    # 3. Install hook scripts to ~/.claude/hooks/
    hooks_dir = claude_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    src_hooks = _ASSETS_DIR / "hooks"
    for hook_name in ("hc-pre-tool-use.sh", "hc-post-tool-use.sh"):
        src = src_hooks / hook_name
        dst = hooks_dir / hook_name
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        dst.chmod(0o755)
    result["hooks_installed"] = True

    # 4. Patch ~/.claude/settings.json
    settings_path = claude_dir / "settings.json"
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    data.setdefault("hooks", {})
    data["hooks"].setdefault("PreToolUse", [])
    data["hooks"].setdefault("PostToolUse", [])

    patched = False
    if not _entry_present(data["hooks"]["PreToolUse"], _HC_HOOK_PATH_PRE):
        data["hooks"]["PreToolUse"].append(_HC_PRE_HOOK_ENTRY)
        patched = True
    if not _entry_present(data["hooks"]["PostToolUse"], _HC_HOOK_PATH_POST):
        data["hooks"]["PostToolUse"].append(_HC_POST_HOOK_ENTRY)
        patched = True

    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    result["settings_patched"] = patched

    return result


@main.command("init")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--global", "global_config", is_flag=True,
    help="Register in ~/.claude/settings.json instead of .claude/settings.json",
)
def cmd_init(path: str, global_config: bool):
    """Index project and register MCP server in Claude Code."""
    root = Path(path).resolve()

    click.echo("hybrid-coco init")
    click.echo("━" * 40)

    # Step 1: index
    click.echo(f"Indexing {root} …")
    result = index_path(root)
    db = get_index_path(root)

    # Count total symbols now
    store = Store(db)
    try:
        stats = store.stats()
    finally:
        store.close()

    click.echo(f"  ✓ {stats['files']} files indexed, {stats['symbols']} symbols")
    click.echo(f"  ✓ Index: {db.relative_to(root)}")
    click.echo()

    # Step 2: register MCP in project settings
    if global_config:
        settings_path = Path.home() / ".claude" / "settings.json"
        label = "~/.claude/settings.json"
    else:
        settings_path = root / ".claude" / "settings.json"
        label = ".claude/settings.json"

    _merge_mcp_settings(settings_path)
    click.echo(f"MCP server registered in {label}")
    for tool in MCP_TOOLS:
        click.echo(f"  ✓ {tool}")
    click.echo()

    # Step 3: global Claude Code integration
    claude_dir = Path.home() / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    global_result = _install_global(claude_dir)

    click.echo("Global Claude Code integration")
    click.echo(f"  ✓ ~/.claude/hybrid-coco.md written")
    if global_result["claude_md_updated"]:
        click.echo(f"  ✓ @hybrid-coco.md added to ~/.claude/CLAUDE.md")
    else:
        click.echo(f"  ✓ @hybrid-coco.md already in ~/.claude/CLAUDE.md")
    click.echo(f"  ✓ Hooks installed in ~/.claude/hooks/")
    click.echo(f"  ✓ PreToolUse: Read|Grep → hc_* suggestion")
    click.echo(f"  ✓ PostToolUse: Write|Edit → hc update")
    click.echo()

    click.echo("Done. Restart Claude Code to activate.")
