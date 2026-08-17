"""Cursor host: project .cursor/mcp.json, hooks.json, and equivalent skills."""

from __future__ import annotations

from pathlib import Path

from .common import (
    MCP_TOOLS,
    copy_skills,
    hook_command,
    load_json_object,
    mcp_registered_json,
    merge_mcp_json,
    remove_mcp_json,
    write_json,
)
from .types import HostResult

_HOOK_EVENTS: tuple[tuple[str, str, str | None], ...] = (
    ("preToolUse", "pre-tool-use", "Read|Grep"),
    ("beforeReadFile", "before-read-file", None),
    ("postToolUse", "post-tool-use", "Write|StrReplace"),
    ("afterFileEdit", "after-file-edit", None),
    ("sessionStart", "session-start", None),
)


def _hooks_file(root: Path, *, global_config: bool, home: Path) -> Path:
    if global_config:
        return home / ".cursor" / "hooks.json"
    return root / ".cursor" / "hooks.json"


def _mcp_file(root: Path, *, global_config: bool, home: Path) -> Path:
    if global_config:
        return home / ".cursor" / "mcp.json"
    return root / ".cursor" / "mcp.json"


def _ensure_hook_entry(entries: list, command: str, matcher: str | None) -> bool:
    for entry in entries:
        if entry.get("command") == command:
            return False
    item: dict[str, str] = {"command": command}
    if matcher is not None:
        item["matcher"] = matcher
    entries.append(item)
    return True


def _patch_hooks_json(path: Path) -> None:
    data = load_json_object(path) if path.is_file() else {}
    data["version"] = 1
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    for event, hc_event, matcher in _HOOK_EVENTS:
        command = hook_command("cursor", hc_event)
        entries = hooks.get(event)
        if not isinstance(entries, list):
            entries = []
            hooks[event] = entries
        _ensure_hook_entry(entries, command, matcher)
    write_json(path, data)


class CursorHost:
    name = "cursor"
    title = "Cursor"
    events = (
        "pre-tool-use",
        "post-tool-use",
        "before-read-file",
        "after-file-edit",
        "session-start",
    )

    def install(self, root: Path, *, global_config: bool, home: Path) -> HostResult:
        lines: list[str] = []
        mcp_path = _mcp_file(root, global_config=global_config, home=home)
        merge_mcp_json(mcp_path)
        label = str(mcp_path) if global_config else ".cursor/mcp.json"
        lines.append(f"MCP server registered in {label}")
        for tool in MCP_TOOLS:
            lines.append(tool)

        hooks_path = _hooks_file(root, global_config=global_config, home=home)
        _patch_hooks_json(hooks_path)
        lines.append(f"hooks registered in {hooks_path}")
        lines.append("preToolUse/beforeReadFile: Read|Grep → hc_* suggestion")
        lines.append("postToolUse/afterFileEdit: Write|StrReplace → hc update")
        lines.append("sessionStart: incremental hc update when an index exists")

        skill_targets = [home / ".cursor" / "skills"]
        if not global_config:
            skill_targets.append(root / ".cursor" / "skills")
        skills: list[str] = []
        for dst in skill_targets:
            skills = copy_skills(dst)
            rel = dst
            if not global_config and dst == root / ".cursor" / "skills":
                rel = Path(".cursor/skills")
            lines.append(f"skills installed in {rel}: {', '.join(skills)}")

        return HostResult(name=self.name, title=self.title, lines=lines, skills=skills)

    def mcp_registered(self, root: Path, *, home: Path) -> bool:
        return mcp_registered_json(root / ".cursor" / "mcp.json") or mcp_registered_json(
            home / ".cursor" / "mcp.json"
        )

    def hooks_present(self, root: Path, *, home: Path) -> bool:
        for path in (root / ".cursor" / "hooks.json", home / ".cursor" / "hooks.json"):
            if not path.is_file():
                continue
            try:
                data = load_json_object(path)
            except ValueError:
                continue
            hooks = data.get("hooks")
            if not isinstance(hooks, dict):
                continue
            if "preToolUse" in hooks and "afterFileEdit" in hooks:
                return True
        return False

    def mcp_locations(self, root: Path, *, home: Path) -> list[Path]:
        return [root / ".cursor" / "mcp.json", home / ".cursor" / "mcp.json"]

    def remove_mcp(self, root: Path, *, home: Path) -> list[str]:
        actions: list[str] = []
        for path in (root / ".cursor" / "mcp.json",):
            msg = remove_mcp_json(path)
            if msg is None:
                actions.append(f"no hybrid-coco MCP entry in {path}")
            else:
                actions.append(msg)
        return actions
