"""shared hook-json patching for agent hosts."""

from __future__ import annotations

from pathlib import Path

from .common import hook_command, load_json_object, write_json

HookEventSpec = tuple[str, str, str | None]


def hook_command_present(entries: list, command: str) -> bool:
    for entry in entries:
        for hook in entry.get("hooks", []):
            if hook.get("command") == command:
                return True
    return False


def flat_hook_command_present(entries: list, command: str) -> bool:
    for entry in entries:
        if entry.get("command") == command:
            return True
    return False


def append_nested_command_hook(
    entries: list,
    command: str,
    matcher: str | None,
) -> bool:
    if hook_command_present(entries, command):
        return False
    item: dict = {"hooks": [{"type": "command", "command": command}]}
    if matcher is not None:
        item["matcher"] = matcher
    entries.append(item)
    return True


def append_flat_command_hook(
    entries: list,
    command: str,
    matcher: str | None,
) -> bool:
    if flat_hook_command_present(entries, command):
        return False
    item: dict[str, str] = {"command": command}
    if matcher is not None:
        item["matcher"] = matcher
    entries.append(item)
    return True


def patch_nested_hook_events(
    path: Path,
    host: str,
    events: HookEventSpec,
) -> None:
    data = load_json_object(path) if path.is_file() else {}
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    for event, hc_event, matcher in events:
        command = hook_command(host, hc_event)
        entries = hooks.get(event)
        if not isinstance(entries, list):
            entries = []
            hooks[event] = entries
        append_nested_command_hook(entries, command, matcher)
    write_json(path, data)


def patch_flat_hook_events(
    path: Path,
    host: str,
    events: HookEventSpec,
    *,
    version: int = 1,
) -> None:
    data = load_json_object(path) if path.is_file() else {}
    data["version"] = version
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    for event, hc_event, matcher in events:
        command = hook_command(host, hc_event)
        entries = hooks.get(event)
        if not isinstance(entries, list):
            entries = []
            hooks[event] = entries
        append_flat_command_hook(entries, command, matcher)
    write_json(path, data)


def patch_devin_hook_events(path: Path, host: str, events: HookEventSpec, *, wrapped: bool) -> None:
    data = load_json_object(path) if path.is_file() else {}
    if wrapped:
        hooks = data.get("hooks")
        if not isinstance(hooks, dict):
            hooks = {}
            data["hooks"] = hooks
        _patch_devin_hook_map(hooks, host, events)
        write_json(path, data)
        return
    _patch_devin_hook_map(data, host, events)
    write_json(path, data)


def _patch_devin_hook_map(hooks: dict, host: str, events: HookEventSpec) -> None:
    for event, hc_event, matcher in events:
        command = hook_command(host, hc_event)
        entries = hooks.get(event)
        if not isinstance(entries, list):
            entries = []
            hooks[event] = entries
        append_nested_command_hook(entries, command, matcher)
