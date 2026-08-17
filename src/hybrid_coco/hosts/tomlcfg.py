"""minimal TOML table upsert for Codex config.toml — no extra dependency."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_TABLE_RE = re.compile(
    r"^\[mcp_servers\.hybrid-coco\][^\[]*",
    re.MULTILINE,
)

MCP_BLOCK = (
    "[mcp_servers.hybrid-coco]\n"
    'command = "hc"\n'
    'args = ["serve"]\n'
)


def upsert_codex_mcp(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text(MCP_BLOCK + "\n", encoding="utf-8")
        tomllib.loads(path.read_text(encoding="utf-8"))
        return
    original = path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(original)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    servers = data.get("mcp_servers")
    if isinstance(servers, dict):
        existing = servers.get("hybrid-coco")
        if (
            isinstance(existing, dict)
            and existing.get("command") == "hc"
            and existing.get("args") == ["serve"]
        ):
            return
    if _TABLE_RE.search(original):
        new = _TABLE_RE.sub(MCP_BLOCK + "\n", original, count=1)
    else:
        sep = "" if original.endswith("\n") or original == "" else "\n"
        new = original + sep + "\n" + MCP_BLOCK + "\n"
    path.write_text(new, encoding="utf-8")
    try:
        tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        path.write_text(original, encoding="utf-8")
        raise ValueError(f"wrote invalid TOML to {path}: {exc}") from exc


def mcp_registered_toml(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return False
    servers = data.get("mcp_servers")
    return isinstance(servers, dict) and "hybrid-coco" in servers


def remove_codex_mcp(path: Path) -> str | None:
    if not path.is_file():
        return None
    original = path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(original)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    servers = data.get("mcp_servers")
    if not isinstance(servers, dict) or "hybrid-coco" not in servers:
        return None
    new, n = _TABLE_RE.subn("", original, count=1)
    if n == 0:
        raise ValueError(f"{path} has mcp_servers.hybrid-coco but no matching table text")
    path.write_text(new, encoding="utf-8")
    try:
        tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        path.write_text(original, encoding="utf-8")
        raise ValueError(f"wrote invalid TOML to {path}: {exc}") from exc
    return f"removed hybrid-coco MCP entry from {path}"
