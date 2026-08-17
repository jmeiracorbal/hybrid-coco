"""Codex host: MCP in .codex/config.toml, Agent Skills, Claude-compatible hooks.json."""

from __future__ import annotations

from pathlib import Path

from .common import MCP_TOOLS, copy_skills, hook_command, load_json_object, skills_src, write_json
from .tomlcfg import mcp_registered_toml, remove_codex_mcp, upsert_codex_mcp
from .instructions import apply_project_instructions
from .types import HostResult

_HOOK_EVENTS: tuple[tuple[str, str, str | None], ...] = (
    ("PreToolUse", "pre-tool-use", "Bash"),
    ("PostToolUse", "post-tool-use", "apply_patch|Edit|Write"),
    ("SessionStart", "session-start", None),
)


def _config_file(root: Path, *, global_config: bool, home: Path) -> Path:
    if global_config:
        return home / ".codex" / "config.toml"
    return root / ".codex" / "config.toml"


def _hooks_file(root: Path, *, global_config: bool, home: Path) -> Path:
    if global_config:
        return home / ".codex" / "hooks.json"
    return root / ".codex" / "hooks.json"


def _command_present(entries: list, command: str) -> bool:
    for entry in entries:
        for hook in entry.get("hooks", []):
            if hook.get("command") == command:
                return True
    return False


def _patch_hooks_json(path: Path) -> None:
    data = load_json_object(path) if path.is_file() else {}
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    for event, hc_event, matcher in _HOOK_EVENTS:
        command = hook_command("codex", hc_event)
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
    write_json(path, data)


class CodexHost:
    name = "codex"
    title = "Codex"
    events = ("pre-tool-use", "post-tool-use", "session-start")

    def install(self, root: Path, *, global_config: bool, home: Path) -> HostResult:
        lines: list[str] = []
        cfg = _config_file(root, global_config=global_config, home=home)
        upsert_codex_mcp(cfg)
        label = str(cfg) if global_config else ".codex/config.toml"
        lines.append(f"MCP server registered in {label}")
        for tool in MCP_TOOLS:
            lines.append(tool)

        hooks_path = _hooks_file(root, global_config=global_config, home=home)
        _patch_hooks_json(hooks_path)
        lines.append(f"hooks registered in {hooks_path}")
        lines.append("PreToolUse Bash: cat/head/rg/grep of indexed files → hc_*")
        lines.append("PostToolUse apply_patch|Edit|Write → hc update")
        lines.append("SessionStart: incremental hc update + hc_* reminder")
        lines.extend(apply_project_instructions(root=root, host=self.name))

        skill_targets = [home / ".agents" / "skills"]
        if not global_config:
            skill_targets.append(root / ".agents" / "skills")
        skills: list[str] = []
        for dst in skill_targets:
            skills = copy_skills(dst, skills_src(self.name))
            rel: Path | str = dst
            if not global_config and dst == root / ".agents" / "skills":
                rel = Path(".agents/skills")
            lines.append(f"skills installed in {rel}: {', '.join(skills)}")

        return HostResult(name=self.name, title=self.title, lines=lines, skills=skills)

    def mcp_registered(self, root: Path, *, home: Path) -> bool:
        return mcp_registered_toml(root / ".codex" / "config.toml") or mcp_registered_toml(
            home / ".codex" / "config.toml"
        )

    def hooks_present(self, root: Path, *, home: Path) -> bool:
        for path in (root / ".codex" / "hooks.json", home / ".codex" / "hooks.json"):
            if not path.is_file():
                continue
            try:
                data = load_json_object(path)
            except ValueError:
                continue
            hooks = data.get("hooks")
            if isinstance(hooks, dict) and "PreToolUse" in hooks and "PostToolUse" in hooks:
                return True
        return False

    def mcp_locations(self, root: Path, *, home: Path) -> list[Path]:
        return [root / ".codex" / "config.toml", home / ".codex" / "config.toml"]

    def remove_mcp(self, root: Path, *, home: Path) -> list[str]:
        path = root / ".codex" / "config.toml"
        msg = remove_codex_mcp(path)
        if msg is None:
            return [f"no hybrid-coco MCP entry in {path}"]
        return [msg]
