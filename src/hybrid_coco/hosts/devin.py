"""Devin host: MCP in .devin/mcp_config.json, Claude-compatible hooks.v1.json."""

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
    skills_src,
    write_json,
)
from .instructions import apply_project_instructions
from .types import HostResult

_HOOK_EVENTS: tuple[tuple[str, str, str | None], ...] = (
    ("PreToolUse", "pre-tool-use", "^(read|grep)$"),
    ("PostToolUse", "post-tool-use", "^(write|edit)$"),
    ("SessionStart", "session-start", None),
)


def _mcp_file(root: Path, *, global_config: bool, home: Path) -> Path:
    if global_config:
        return home / ".config" / "devin" / "mcp_config.json"
    return root / ".devin" / "mcp_config.json"


def _hooks_file(root: Path, *, global_config: bool, home: Path) -> Path:
    if global_config:
        return home / ".config" / "devin" / "config.json"
    return root / ".devin" / "hooks.v1.json"


def _command_present(entries: list, command: str) -> bool:
    for entry in entries:
        for hook in entry.get("hooks", []):
            if hook.get("command") == command:
                return True
    return False


def _patch_hook_map(hooks: dict) -> None:
    for event, hc_event, matcher in _HOOK_EVENTS:
        command = hook_command("devin", hc_event)
        entries = hooks.get(event)
        if not isinstance(entries, list):
            entries = []
            hooks[event] = entries
        if _command_present(entries, command):
            continue
        item: dict = {
            "hooks": [{"type": "command", "command": command}],
        }
        if matcher is not None:
            item["matcher"] = matcher
        entries.append(item)


def _patch_hooks(path: Path, *, wrapped: bool) -> None:
    data = load_json_object(path) if path.is_file() else {}
    if wrapped:
        hooks = data.get("hooks")
        if not isinstance(hooks, dict):
            hooks = {}
            data["hooks"] = hooks
        _patch_hook_map(hooks)
        write_json(path, data)
        return
    _patch_hook_map(data)
    write_json(path, data)


class DevinHost:
    name = "devin"
    title = "Devin"
    events = ("pre-tool-use", "post-tool-use", "session-start")

    def install(self, root: Path, *, global_config: bool, home: Path) -> HostResult:
        lines: list[str] = []
        mcp_path = _mcp_file(root, global_config=global_config, home=home)
        merge_mcp_json(mcp_path)
        label = str(mcp_path) if global_config else ".devin/mcp_config.json"
        lines.append(f"MCP server registered in {label}")
        for tool in MCP_TOOLS:
            lines.append(tool)

        hooks_path = _hooks_file(root, global_config=global_config, home=home)
        _patch_hooks(hooks_path, wrapped=global_config)
        lines.append(f"hooks registered in {hooks_path}")
        lines.append("PreToolUse ^(read|grep)$ → hc_*")
        lines.append("PostToolUse ^(write|edit)$ → hc update")
        lines.append("SessionStart: incremental hc update + hc_* reminder")
        lines.extend(apply_project_instructions(root=root, host=self.name))

        skill_targets = [home / ".config" / "devin" / "skills"]
        if not global_config:
            skill_targets.append(root / ".devin" / "skills")
        skills: list[str] = []
        for dst in skill_targets:
            skills = copy_skills(dst, skills_src(self.name))
            rel: Path | str = dst
            if not global_config and dst == root / ".devin" / "skills":
                rel = Path(".devin/skills")
            lines.append(f"skills installed in {rel}: {', '.join(skills)}")

        return HostResult(name=self.name, title=self.title, lines=lines, skills=skills)

    def mcp_registered(self, root: Path, *, home: Path) -> bool:
        return mcp_registered_json(root / ".devin" / "mcp_config.json") or mcp_registered_json(
            home / ".config" / "devin" / "mcp_config.json"
        )

    def hooks_present(self, root: Path, *, home: Path) -> bool:
        project = root / ".devin" / "hooks.v1.json"
        if project.is_file():
            try:
                data = load_json_object(project)
            except ValueError:
                data = {}
            if "PreToolUse" in data and "PostToolUse" in data:
                return True
        global_cfg = home / ".config" / "devin" / "config.json"
        if global_cfg.is_file():
            try:
                data = load_json_object(global_cfg)
            except ValueError:
                return False
            hooks = data.get("hooks")
            return isinstance(hooks, dict) and "PreToolUse" in hooks
        return False

    def mcp_locations(self, root: Path, *, home: Path) -> list[Path]:
        return [
            root / ".devin" / "mcp_config.json",
            home / ".config" / "devin" / "mcp_config.json",
        ]

    def remove_mcp(self, root: Path, *, home: Path) -> list[str]:
        path = root / ".devin" / "mcp_config.json"
        msg = remove_mcp_json(path)
        if msg is None:
            return [f"no hybrid-coco MCP entry in {path}"]
        return [msg]
