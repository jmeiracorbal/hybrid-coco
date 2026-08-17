"""agent host registry — Claude Code is default; extra hosts opt in via --host."""

from __future__ import annotations

from pathlib import Path

from .claude import ClaudeHost
from .codex import CodexHost
from .cursor import CursorHost
from .devin import DevinHost
from .opencode import OpenCodeHost
from .types import HostResult

_HOSTS = {
    "claude": ClaudeHost(),
    "cursor": CursorHost(),
    "codex": CodexHost(),
    "opencode": OpenCodeHost(),
    "devin": DevinHost(),
}

HOST_NAMES = tuple(_HOSTS.keys())


def require_host(name: str):
    if name not in _HOSTS:
        valid = ", ".join(HOST_NAMES)
        raise ValueError(f"unknown host: {name}. valid: {valid}")
    return _HOSTS[name]


def resolve_host_names(requested: tuple[str, ...]) -> tuple[str, ...]:
    if not requested:
        raise ValueError("host list is empty")
    if "all" in requested:
        if requested != ("all",):
            raise ValueError("'all' cannot be combined with other --host values")
        return HOST_NAMES
    seen: list[str] = []
    for name in requested:
        require_host(name)
        if name not in seen:
            seen.append(name)
    return tuple(seen)


def install_hosts(
    root: Path,
    names: tuple[str, ...],
    *,
    global_config: bool,
    home: Path,
) -> list[HostResult]:
    results: list[HostResult] = []
    for name in names:
        results.append(
            require_host(name).install(root, global_config=global_config, home=home)
        )
    return results


def iter_hosts():
    return _HOSTS.items()
