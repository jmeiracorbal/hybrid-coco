"""shared install helpers for agent hosts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

HOST_NAMES: tuple[str, ...] = ("claude", "cursor", "codex", "opencode", "devin")

MCP_COMMAND = "hc"
MCP_ARGS = ["serve"]
MCP_ENTRY = {
    "command": MCP_COMMAND,
    "args": MCP_ARGS,
    "type": "stdio",
}
MCP_TOOLS = [
    "hc_search",
    "hc_symbol",
    "hc_file_context",
    "hc_snippet",
    "hc_structure",
    "hc_status",
]
SKILL_NAMES = ("hybrid-coco", "hc-init", "hc-search")


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def merge_mcp_json(path: Path, *, servers_key: str = "mcpServers") -> None:
    data = load_json_object(path) if path.is_file() else {}
    servers = data.get(servers_key)
    if servers is None:
        servers = {}
        data[servers_key] = servers
    if not isinstance(servers, dict):
        raise ValueError(f"{path}: {servers_key} must be an object")
    servers["hybrid-coco"] = dict(MCP_ENTRY)
    write_json(path, data)


def remove_mcp_json(path: Path, *, servers_key: str = "mcpServers") -> str | None:
    if not path.is_file():
        return None
    data = load_json_object(path)
    servers = data.get(servers_key)
    if not isinstance(servers, dict) or "hybrid-coco" not in servers:
        return None
    del servers["hybrid-coco"]
    write_json(path, data)
    return f"removed hybrid-coco MCP entry from {path}"


def mcp_registered_json(path: Path, *, servers_key: str = "mcpServers") -> bool:
    if not path.is_file():
        return False
    try:
        data = load_json_object(path)
    except ValueError:
        return False
    servers = data.get(servers_key)
    return isinstance(servers, dict) and "hybrid-coco" in servers


def skills_src(host: str) -> Path:
    if host not in HOST_NAMES:
        raise ValueError(f"unknown host: {host}")
    roots = {
        "claude": ASSETS_DIR / "skills",
        "cursor": ASSETS_DIR / "hosts" / "cursor" / "skills",
        "codex": ASSETS_DIR / "hosts" / "codex" / "skills",
        "opencode": ASSETS_DIR / "hosts" / "opencode" / "skills",
        "devin": ASSETS_DIR / "hosts" / "devin" / "skills",
    }
    src = roots[host]
    if not src.is_dir():
        raise FileNotFoundError(f"packaged skills missing for host {host}: {src}")
    return src


def copy_skills(dst_root: Path, src_root: Path) -> list[str]:
    if not src_root.is_dir():
        raise FileNotFoundError(f"packaged skills missing at {src_root}")

    installed: list[str] = []
    for name in SKILL_NAMES:
        skill_dir = src_root / name
        skill_md = skill_dir / "SKILL.md"
        if not skill_dir.is_dir() or not skill_md.is_file():
            raise FileNotFoundError(f"packaged skill missing: {skill_dir}")
        dst = dst_root / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(skill_dir, dst)
        installed.append(name)
    return installed


def copy_hook_scripts(dst_dir: Path, names: tuple[str, ...]) -> None:
    src_hooks = ASSETS_DIR / "hooks"
    dst_dir.mkdir(parents=True, exist_ok=True)
    for hook_name in names:
        src = src_hooks / hook_name
        if not src.is_file():
            raise FileNotFoundError(f"packaged hook missing: {src}")
        dst = dst_dir / hook_name
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        dst.chmod(0o755)


def hook_command(host: str, event: str) -> str:
    return f"hc hook {host} {event}"
