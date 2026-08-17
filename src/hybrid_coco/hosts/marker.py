"""project activation marker — mnemo-style `.mnemo`, stored under `.hybrid-coco/`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import HC_DIR

MARKER_FILE = "project.json"
MARKER_VERSION = 1
VALID_AGENTS = ("claude", "cursor", "codex", "opencode", "devin")


def marker_path(root: Path) -> Path:
    return root / HC_DIR / MARKER_FILE


def _require_marker(data: Any, *, path: Path) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    if "version" not in data:
        raise ValueError(f"{path} missing required key: version")
    if "agents" not in data:
        raise ValueError(f"{path} missing required key: agents")
    if not isinstance(data["version"], int):
        raise ValueError(f"{path}: version must be an integer")
    if data["version"] != MARKER_VERSION:
        raise ValueError(f"{path}: unsupported version {data['version']}")
    agents = data["agents"]
    if not isinstance(agents, list) or not all(isinstance(a, str) for a in agents):
        raise ValueError(f"{path}: agents must be a list of strings")
    return data


def read_marker(root: Path) -> dict[str, Any] | None:
    path = marker_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    return _require_marker(data, path=path)


def add_agent(root: Path, agent: str) -> bool:
    if agent not in VALID_AGENTS:
        raise ValueError(f"unknown host: {agent}")
    path = marker_path(root)
    existing = read_marker(root)
    if existing is None:
        data = {"version": MARKER_VERSION, "agents": [agent]}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return True
    agents: list[str] = list(existing["agents"])
    if agent in agents:
        return False
    agents.append(agent)
    existing["agents"] = agents
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return True
