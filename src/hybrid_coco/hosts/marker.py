"""project activation marker — same contract as mnemo's `.mnemo`."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ..config import HC_DIR

MARKER_FILE = "project.json"
MARKER_VERSION = 1
from .common import HOST_NAMES as VALID_AGENTS

# fixed forever — changing this would invalidate existing project IDs.
_NAMESPACE = uuid.UUID("a7c1e5d0-9b2f-4e8a-b3c4-1d2e3f4a5b6c")


def marker_path(root: Path) -> Path:
    return root / HC_DIR / MARKER_FILE


def project_id_from_path(abs_path: Path) -> str:
    if not abs_path.is_absolute():
        raise ValueError(f"project path must be absolute, got: {abs_path}")
    return str(uuid.uuid5(_NAMESPACE, str(abs_path)))


def _is_canonical_id(ident: Any, abs_root: Path) -> bool:
    if not isinstance(ident, str) or ident == "":
        return False
    try:
        uuid.UUID(ident)
    except ValueError:
        return False
    return ident == project_id_from_path(abs_root)


def _require_marker(data: Any, *, path: Path) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    for key in ("version", "id", "agents"):
        if key not in data:
            raise ValueError(f"{path} missing required key: {key}")
    if not isinstance(data["version"], int):
        raise ValueError(f"{path}: version must be an integer")
    if data["version"] != MARKER_VERSION:
        raise ValueError(f"{path}: unsupported version {data['version']}")
    ident = data["id"]
    if not isinstance(ident, str) or ident == "":
        raise ValueError(f"{path}: id must be a non-empty string")
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


def repair_marker_id(root: Path) -> bool:
    """rewrite `id` to the path uuid5 when it is missing or not canonical.

    does not create a marker. does not invent `version` or `agents`.
    returns True only when the file was written.
    """
    abs_root = root.resolve()
    path = marker_path(abs_root)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(data, dict):
        return False
    if "version" not in data or "agents" not in data:
        return False
    if not isinstance(data["version"], int) or data["version"] != MARKER_VERSION:
        return False
    agents = data["agents"]
    if not isinstance(agents, list) or not all(isinstance(a, str) for a in agents):
        return False
    expected = project_id_from_path(abs_root)
    if data.get("id") == expected:
        return False
    data["id"] = expected
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


def marker_is_active(root: Path) -> bool:
    """true only when the marker exists, is valid, and has a canonical id."""
    try:
        repair_marker_id(root)
        data = read_marker(root)
    except (ValueError, OSError):
        return False
    if data is None:
        return False
    return _is_canonical_id(data["id"], root.resolve())


def add_agent(root: Path, agent: str) -> bool:
    if agent not in VALID_AGENTS:
        raise ValueError(f"unknown host: {agent}")
    abs_root = root.resolve()
    if not abs_root.is_absolute():
        raise ValueError(f"project path must be absolute, got: {root}")
    path = marker_path(abs_root)
    repair_marker_id(abs_root)
    existing = read_marker(abs_root)
    if existing is None:
        data = {
            "version": MARKER_VERSION,
            "id": project_id_from_path(abs_root),
            "agents": [agent],
        }
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
