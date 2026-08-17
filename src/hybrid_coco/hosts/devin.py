"""Devin host: MCP in .devin/mcp_config.json, Claude-compatible hooks.v1.json."""

from __future__ import annotations

from pathlib import Path

from .base import JsonMcpHostInstaller
from .common import load_json_object
from .hooks_patch import patch_devin_hook_events
from .types import HostResult

_HOOK_EVENTS = (
    ("PreToolUse", "pre-tool-use", "^(read|grep)$"),
    ("PostToolUse", "post-tool-use", "^(write|edit)$"),
    ("SessionStart", "session-start", None),
)


class DevinHost(JsonMcpHostInstaller):
    name = "devin"
    title = "Devin"
    events = ("pre-tool-use", "post-tool-use", "session-start")
    project_mcp_rel = Path(".devin") / "mcp_config.json"
    global_mcp_rel = Path(".config") / "devin" / "mcp_config.json"
    project_mcp_label = ".devin/mcp_config.json"

    def _hooks_path(self, root: Path, *, global_config: bool, home: Path) -> Path:
        if global_config:
            return home / ".config" / "devin" / "config.json"
        return root / ".devin" / "hooks.v1.json"

    def install(self, root: Path, *, global_config: bool, home: Path) -> HostResult:
        lines = self.register_mcp(root, global_config=global_config, home=home)

        hooks_path = self._hooks_path(root, global_config=global_config, home=home)
        patch_devin_hook_events(hooks_path, self.name, _HOOK_EVENTS, wrapped=global_config)
        lines.append(f"hooks registered in {hooks_path}")
        lines.append("PreToolUse ^(read|grep)$ → hc_*")
        lines.append("PostToolUse ^(write|edit)$ → hc update")
        lines.append("SessionStart: incremental hc update + hc_* reminder")
        lines.extend(self._apply_project(root))

        skills, skill_lines = self.install_skills(
            root,
            global_config=global_config,
            home=home,
            home_skills=home / ".config" / "devin" / "skills",
            project_skills=root / ".devin" / "skills",
            project_label=Path(".devin/skills"),
        )
        lines.extend(skill_lines)
        return HostResult(name=self.name, title=self.title, lines=lines, skills=skills)

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
