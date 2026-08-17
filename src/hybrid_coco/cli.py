"""CLI entry point for hybrid-coco (hc)."""

from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path

import click

from . import __version__
from .config import get_index_path
from .filters import DEFAULT_QUERY_LIMIT, validate_languages, validate_paging, validate_path_filter
from .indexer import build_exclude_spec, ensure_hc_gitignore, index_path
from .hosts import HOST_NAMES, install_hosts, resolve_host_names
from .hosts.instructions import install_global_instructions, strip_legacy_global_claude_include
from .settings import SettingsError, ensure_settings, load_or_create_settings, settings_path
from .snippet import SnippetError, read_snippet
from .store import Store
from .structure import StructureError, search_structure, validate_structure_kind


def _parse_exclude(exclude: tuple[str, ...]) -> tuple[str, ...]:
    """Validate --exclude patterns; exit on empty/whitespace entries."""
    try:
        build_exclude_spec(exclude)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    return exclude


def _parse_query_filters(
    *,
    path: str | None,
    lang: tuple[str, ...],
    offset: int,
    limit: int,
) -> tuple[str | None, tuple[str, ...], int, int]:
    try:
        path_f = validate_path_filter(path)
        langs = validate_languages(lang)
        validate_paging(offset=offset, limit=limit)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    return path_f, langs, offset, limit

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
@click.version_option(__version__, prog_name="hc")
def main():
    """hybrid-coco — local code intelligence."""


# ── hc index ─────────────────────────────────────────────────────────────────

@main.command("index")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--exclude",
    multiple=True,
    help="Additional gitignore-style patterns to exclude (repeatable)",
)
@click.option("--verbose", "-v", is_flag=True)
def cmd_index(path: str, exclude: tuple, verbose: bool):
    """Index PATH (default: current directory)."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    patterns = _parse_exclude(exclude)
    root = Path(path).resolve()
    click.echo(f"Indexing {root} …", err=True)
    try:
        result = index_path(root, exclude=patterns)
    except SettingsError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    msg = (
        f"Done. Indexed: {result.indexed}  Skipped (unchanged): {result.skipped}  "
        f"Errors: {result.errors}"
    )
    if result.removed:
        msg += f"  Removed: {result.removed}"
    click.echo(msg)


# ── hc update ────────────────────────────────────────────────────────────────

@main.command("update")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--exclude",
    multiple=True,
    help="Additional gitignore-style patterns to exclude (repeatable)",
)
@click.option("--verbose", "-v", is_flag=True)
def cmd_update(path: str, exclude: tuple, verbose: bool):
    """Re-index only changed files in PATH."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    patterns = _parse_exclude(exclude)
    root = Path(path).resolve()
    db = get_index_path(root)
    if not db.exists():
        click.echo(f"No index found. Run: hc index {root}", err=True)
        sys.exit(1)

    click.echo(f"Updating {root} …", err=True)
    try:
        result = index_path(root, force=False, exclude=patterns)
    except SettingsError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    msg = (
        f"Done. Re-indexed: {result.indexed}  Unchanged: {result.skipped}  "
        f"Errors: {result.errors}"
    )
    if result.removed:
        msg += f"  Removed: {result.removed}"
    click.echo(msg)


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
@click.option("--path", "path_filter", default=None, help="gitignore-style path filter")
@click.option("--lang", multiple=True, help="Language filter (repeatable), e.g. python")
@click.option("--offset", default=0, show_default=True, type=int)
@click.option("--limit", default=DEFAULT_QUERY_LIMIT, show_default=True, type=int)
def cmd_query(text: str, path_filter: str | None, lang: tuple, offset: int, limit: int):
    """FTS5 search across symbol names, signatures and docstrings."""
    path_f, langs, offset, limit = _parse_query_filters(
        path=path_filter, lang=lang, offset=offset, limit=limit
    )
    root = Path.cwd()
    store = _require_store(root)
    try:
        results = store.fts_search(
            text, path=path_f, languages=langs, offset=offset, limit=limit
        )
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
@click.option("--path", "path_filter", default=None, help="gitignore-style path filter")
@click.option("--lang", multiple=True, help="Language filter (repeatable), e.g. python")
@click.option("--offset", default=0, show_default=True, type=int)
@click.option("--limit", default=DEFAULT_QUERY_LIMIT, show_default=True, type=int)
def cmd_symbol(name: str, path_filter: str | None, lang: tuple, offset: int, limit: int):
    """Lookup a symbol by name (exact, then prefix)."""
    path_f, langs, offset, limit = _parse_query_filters(
        path=path_filter, lang=lang, offset=offset, limit=limit
    )
    root = Path.cwd()
    store = _require_store(root)
    try:
        results = store.lookup_symbol(
            name, path=path_f, languages=langs, offset=offset, limit=limit
        )
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


# ── hc snippet ───────────────────────────────────────────────────────────────

@main.command("snippet")
@click.argument("path")
@click.argument("line_start", type=int)
@click.argument("line_end", type=int)
def cmd_snippet(path: str, line_start: int, line_end: int):
    """Read PATH lines LINE_START..LINE_END from disk (1-based, inclusive)."""
    root = Path.cwd()
    try:
        click.echo(read_snippet(root, path, line_start, line_end))
    except SnippetError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ── hc structure ─────────────────────────────────────────────────────────────

@main.command("structure")
@click.argument("kind")
@click.option("--path", "path_filter", default=None, help="gitignore-style path filter")
@click.option("--lang", multiple=True, help="Language filter (repeatable), e.g. python")
@click.option("--offset", default=0, show_default=True, type=int)
@click.option("--limit", default=DEFAULT_QUERY_LIMIT, show_default=True, type=int)
def cmd_structure(kind: str, path_filter: str | None, lang: tuple, offset: int, limit: int):
    """Find code by tree-sitter shape: function, method, class, or import."""
    try:
        validate_structure_kind(kind)
    except StructureError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    root = Path.cwd()
    store = _require_store(root)
    try:
        results = search_structure(
            root,
            store,
            kind,
            path=path_filter,
            languages=lang,
            offset=offset,
            limit=limit,
        )
    except (StructureError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    finally:
        store.close()

    if not results:
        click.echo("No results.")
        return

    for match in results:
        label = match.name if match.name else match.node_type
        click.echo(
            f"[{match.path}:{match.line_start}] {match.kind} {label} ({match.language})"
        )
        if match.preview:
            click.echo(f"  {match.preview}")


# ── hc serve ─────────────────────────────────────────────────────────────────

@main.command("serve")
def cmd_serve():
    """Start MCP server (stdio). Register with: hc init"""
    from .server import run_server
    run_server(Path.cwd())


# ── hc doctor ────────────────────────────────────────────────────────────────

@main.command("doctor")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
def cmd_doctor(path: str):
    """Run diagnostics: index, schema, languages, MCP/hooks, version alignment."""
    from .doctor import format_report, run_doctor

    root = Path(path).resolve()
    report = run_doctor(root)
    click.echo(format_report(report))
    if not report.ok:
        sys.exit(1)


# ── hc reset ─────────────────────────────────────────────────────────────────

@main.command("reset")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("-f", "--force", is_flag=True, help="Skip confirmation prompt")
@click.option(
    "--all",
    "wipe_all",
    is_flag=True,
    help="Also remove hybrid-coco MCP entries from registered agent hosts",
)
def cmd_reset(path: str, force: bool, wipe_all: bool):
    """Delete the local index database (and optionally project MCP settings)."""
    from .doctor import reset_index

    root = Path(path).resolve()
    db = get_index_path(root)
    if not force:
        parts = [f"Delete index at {db}"]
        if wipe_all:
            parts.append("and hybrid-coco MCP entries from agent host configs")
        click.confirm(" ".join(parts) + "?", abort=True)

    try:
        actions = reset_index(root, wipe_settings=wipe_all)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    for line in actions:
        click.echo(f"  ✓ {line}")
    click.echo("Done. Run: hc index " + str(root))


# ── hc hook ──────────────────────────────────────────────────────────────────

@main.command("hook")
@click.argument("host")
@click.argument("event")
def cmd_hook(host: str, event: str):
    """Run a host lifecycle hook (JSON on stdin/stdout). Used by agent hosts."""
    from .hosts.runtime import run_hook

    code = run_hook(host, event, sys.stdin.read(), Path.cwd())
    sys.exit(code)


# ── hc install-instructions ──────────────────────────────────────────────────

@main.command("install-instructions")
@click.option(
    "--host",
    "host_names",
    multiple=True,
    default=("claude",),
    show_default=True,
    help=(
        "Agent host whose global instruction surface to update (repeatable). "
        f"One of: {', '.join(HOST_NAMES)}, or all."
    ),
)
def cmd_install_instructions(host_names: tuple[str, ...]):
    """Install the short conditional protocol into user-global instruction files."""
    try:
        names = resolve_host_names(host_names)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    home = Path.home()
    click.echo("hybrid-coco install-instructions")
    click.echo("━" * 40)
    try:
        if "claude" in names:
            for line in strip_legacy_global_claude_include(home):
                click.echo(f"  ✓ {line}")
        for name in names:
            dest = install_global_instructions(home=home, host=name)
            click.echo(f"  ✓ {dest}")
    except (OSError, ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    click.echo("Done. Restart the agent host to load the updated instructions.")


# ── hc init ──────────────────────────────────────────────────────────────────

@main.command("init")
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--host",
    "host_names",
    multiple=True,
    default=("claude",),
    show_default=True,
    help=(
        "Agent host to register (repeatable). "
        f"One of: {', '.join(HOST_NAMES)}, or all."
    ),
)
@click.option(
    "--global", "global_config", is_flag=True,
    help="Register MCP in the user-level host config instead of the project config",
)
def cmd_init(path: str, host_names: tuple[str, ...], global_config: bool):
    """Index project and register MCP, skills, and hooks for agent hosts."""
    try:
        names = resolve_host_names(host_names)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    root = Path(path).resolve()
    home = Path.home()

    click.echo("hybrid-coco init")
    click.echo("━" * 40)

    click.echo(f"Indexing {root} …")
    created_cfg = ensure_settings(root)
    try:
        index_path(root)
    except SettingsError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    db = get_index_path(root)

    store = Store(db)
    try:
        stats = store.stats()
    finally:
        store.close()

    click.echo(f"  ✓ {stats['files']} files indexed, {stats['symbols']} symbols")
    click.echo(f"  ✓ Index: {db.relative_to(root)}")

    if ensure_hc_gitignore(root):
        click.echo(f"  ✓ Added {root / '.gitignore'} entry for .hybrid-coco/")
    else:
        click.echo("  ✓ .hybrid-coco/ already in .gitignore")
    cfg = settings_path(root)
    if created_cfg:
        click.echo(f"  ✓ Wrote {cfg.relative_to(root)}")
    else:
        click.echo(f"  ✓ {cfg.relative_to(root)} already present")
    click.echo()

    try:
        results = install_hosts(root, names, global_config=global_config, home=home)
    except (OSError, ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    for result in results:
        click.echo(f"{result.title} integration")
        for line in result.lines:
            click.echo(f"  ✓ {line}")
        click.echo()

    titles = ", ".join(result.title for result in results)
    click.echo(f"Done. Restart {titles} to activate.")
