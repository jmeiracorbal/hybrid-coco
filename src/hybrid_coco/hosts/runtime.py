"""host-agnostic intercept logic for agent lifecycle hooks."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import get_index_path
from ..indexer import index_path
from ..settings import SettingsError
from ..snippet import SnippetError, read_snippet
from ..store import Store
from .marker import marker_is_active

_GREP_META = re.compile(r"[.^$*+?{}\[\]\\|()]")
_SHELL_CAT = re.compile(r"^(?:cat|bat)\s+(\S+)$")
_SHELL_HEAD = re.compile(r"^head(?:\s+-n\s+(\d+))?\s+(\S+)$")
_SHELL_GREP = re.compile(r"^(?:rg|grep)\s+(\S+)$")

READ_TOOLS = frozenset({"Read", "read"})
GREP_TOOLS = frozenset({"Grep", "grep"})
WRITE_TOOLS = frozenset({
    "Write",
    "write",
    "Edit",
    "edit",
    "StrReplace",
    "apply_patch",
})
SHELL_TOOLS = frozenset({"Bash", "shell", "exec"})

READ_PATH_KEYS: dict[str, tuple[str, ...]] = {
    "claude": ("file_path",),
    "cursor": ("path", "file_path"),
    "codex": (),
    "opencode": ("filePath",),
    "devin": ("file_path",),
}


@dataclass(frozen=True)
class HookResult:
    block: bool
    message: str


def find_index_root(start: Path) -> Path | None:
    """walk up until both the index and a valid project marker exist.

    same gate as mnemo: missing/malformed marker or empty id → inactive.
    an index without `hc init` (no `project.json` id) does not activate hooks.
    """
    current = start.resolve()
    while True:
        if (current / ".hybrid-coco" / "index.db").is_file() and marker_is_active(current):
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _indexed_relpath(root: Path, file_path: str) -> str | None:
    path = Path(file_path)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return None


def _format_file_context(path: str, data: dict) -> str:
    symbols = data["symbols"]
    lang = data["language"] or "unknown"
    lines = [f"File: {path} ({lang}) — {len(symbols)} symbols", ""]
    by_kind: dict[str, list[dict]] = {}
    for sym in symbols:
        by_kind.setdefault(sym["kind"], []).append(sym)
    labels = {
        "class": "Classes",
        "function": "Functions",
        "method": "Methods",
        "import": "Imports",
    }
    for kind, label in labels.items():
        group = by_kind.get(kind)
        if not group:
            continue
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


def _format_search(pattern: str, rows: list[dict]) -> str:
    lines = [f'Search results for "{pattern}":', ""]
    for r in rows:
        doc_part = f" — {r['docstring'][:80]}" if r.get("docstring") else ""
        lines.append(f"[{r['path']}:{r['line_start']}]  {r['kind']} {r['name']}{doc_part}")
    return "\n".join(lines)


def intercept_read(root: Path, rel_path: str, offset: int | None, limit: int | None) -> str | None:
    store = Store(get_index_path(root))
    try:
        if store.get_file(rel_path) is None:
            return None
        if isinstance(offset, int) and isinstance(limit, int):
            line_end = offset + limit - 1
            try:
                body = read_snippet(root, rel_path, offset, line_end)
            except SnippetError:
                return None
            return (
                f"[hybrid-coco] Snippet for {rel_path}:\n\n{body}\n\n"
                "Use hc_snippet when line ranges are known."
            )
        data = store.file_context(rel_path)
        if data is None:
            return None
        body = _format_file_context(rel_path, data)
        return (
            f"[hybrid-coco] Symbols for {rel_path}:\n\n{body}\n\n"
            "Use hc_file_context first, then hc_snippet for the body."
        )
    finally:
        store.close()


def intercept_grep(root: Path, pattern: str) -> str | None:
    if _GREP_META.search(pattern):
        return None
    store = Store(get_index_path(root))
    try:
        rows = store.fts_search(pattern)
    finally:
        store.close()
    if not rows:
        return None
    body = _format_search(pattern, rows)
    return (
        f"[hybrid-coco] {body}\n\n"
        "Use hc_search, then hc_snippet for matched ranges."
    )


def refresh_index(root: Path) -> None:
    try:
        index_path(root, force=False)
    except (OSError, SettingsError, ValueError) as exc:
        print(f"hybrid-coco: hc update failed: {exc}", file=sys.stderr)


def _read_path_from_input(host: str, tool_input: dict[str, Any]) -> str | None:
    keys = READ_PATH_KEYS[host]
    for key in keys:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _offset_limit(tool_input: dict[str, Any]) -> tuple[int | None, int | None]:
    offset = tool_input.get("offset")
    limit = tool_input.get("limit")
    off = offset if isinstance(offset, int) else None
    lim = limit if isinstance(limit, int) else None
    return off, lim


def _shell_intercept(root: Path, command: str) -> str | None:
    stripped = command.strip()
    cat = _SHELL_CAT.match(stripped)
    if cat:
        rel = _indexed_relpath(root, cat.group(1))
        if rel is None:
            return None
        return intercept_read(root, rel, None, None)
    head = _SHELL_HEAD.match(stripped)
    if head:
        rel = _indexed_relpath(root, head.group(2))
        if rel is None:
            return None
        n = int(head.group(1)) if head.group(1) else None
        if n is None:
            return intercept_read(root, rel, None, None)
        return intercept_read(root, rel, 1, n)
    grep = _SHELL_GREP.match(stripped)
    if grep:
        return intercept_grep(root, grep.group(1))
    return None


def handle_pre_tool_use(host: str, payload: dict[str, Any], cwd: Path) -> HookResult | None:
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or not tool:
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    root = find_index_root(cwd)
    if root is None:
        return None

    if tool in READ_TOOLS:
        raw_path = _read_path_from_input(host, tool_input)
        if raw_path is None:
            return None
        rel = _indexed_relpath(root, raw_path)
        if rel is None:
            return None
        offset, limit = _offset_limit(tool_input)
        message = intercept_read(root, rel, offset, limit)
        if message is None:
            return None
        return HookResult(True, message)

    if tool in GREP_TOOLS:
        pattern = tool_input.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            return None
        message = intercept_grep(root, pattern)
        if message is None:
            return None
        return HookResult(True, message)

    if tool in SHELL_TOOLS:
        command = tool_input.get("command")
        if not isinstance(command, str) or not command:
            return None
        message = _shell_intercept(root, command)
        if message is None:
            return None
        return HookResult(True, message)

    return None


def handle_before_read_file(payload: dict[str, Any], cwd: Path) -> HookResult | None:
    file_path = payload.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return None
    root = find_index_root(cwd)
    if root is None:
        return None
    rel = _indexed_relpath(root, file_path)
    if rel is None:
        return None
    message = intercept_read(root, rel, None, None)
    if message is None:
        return None
    return HookResult(True, message)


def handle_post_write(payload: dict[str, Any], cwd: Path) -> None:
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or tool not in WRITE_TOOLS:
        return
    root = find_index_root(cwd)
    if root is None:
        return
    refresh_index(root)


def handle_after_file_edit(payload: dict[str, Any], cwd: Path) -> None:
    file_path = payload.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        root = find_index_root(cwd)
    else:
        path = Path(file_path)
        start = path.parent if path.is_absolute() else cwd
        root = find_index_root(start)
        if root is None:
            root = find_index_root(cwd)
    if root is None:
        return
    refresh_index(root)


def handle_session_start(cwd: Path) -> str | None:
    root = find_index_root(cwd)
    if root is None:
        return None
    refresh_index(root)
    return (
        "hybrid-coco index is present. Prefer hc_* MCP tools "
        "(hc_file_context, hc_symbol, hc_search, hc_snippet, hc_structure) "
        "over full-file Read/Grep."
    )


def format_block(host: str, message: str) -> dict[str, Any]:
    if host == "cursor":
        return {
            "permission": "deny",
            "agent_message": message,
            "user_message": "hybrid-coco intercepted a full-file read",
        }
    if host in {"claude", "codex", "devin"}:
        return {"decision": "block", "reason": message}
    if host == "opencode":
        return {"block": True, "reason": message}
    raise ValueError(f"unknown host: {host}")


def format_session_start(host: str, message: str) -> dict[str, Any]:
    if host == "cursor":
        return {"additional_context": message}
    if host in {"claude", "codex", "devin"}:
        return {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": message,
            }
        }
    if host == "opencode":
        return {"additionalContext": message}
    raise ValueError(f"unknown host: {host}")


def dispatch(host: str, event: str, payload: dict[str, Any], cwd: Path) -> dict[str, Any] | None:
    if event == "pre-tool-use":
        result = handle_pre_tool_use(host, payload, cwd)
        if result is None:
            return None
        return format_block(host, result.message)
    if event == "before-read-file":
        result = handle_before_read_file(payload, cwd)
        if result is None:
            return None
        return format_block(host, result.message)
    if event == "post-tool-use":
        handle_post_write(payload, cwd)
        return None
    if event == "after-file-edit":
        handle_after_file_edit(payload, cwd)
        return None
    if event == "session-start":
        message = handle_session_start(cwd)
        if message is None:
            return None
        return format_session_start(host, message)
    raise ValueError(f"unknown event: {event}")


def read_payload(raw: str) -> dict[str, Any]:
    if not raw.strip():
        raise ValueError("hook stdin is empty")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"hook stdin is not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("hook stdin must be a JSON object")
    return data


def run_hook(host: str, event: str, raw: str, cwd: Path) -> int:
    from . import require_host

    try:
        host_obj = require_host(host)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if event not in host_obj.events:
        print(f"Error: host {host} does not support event {event}", file=sys.stderr)
        return 1
    if event == "session-start" and not raw.strip():
        payload = {}
    else:
        try:
            payload = read_payload(raw)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 0
    try:
        output = dispatch(host, event, payload, cwd)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if output is not None:
        sys.stdout.write(json.dumps(output) + "\n")
    return 0
