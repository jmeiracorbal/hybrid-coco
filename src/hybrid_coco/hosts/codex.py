"""Codex host: MCP in .codex/config.toml, Agent Skills, Claude-compatible hooks.json."""

from __future__ import annotations

from pathlib import Path

from .base import HostInstaller, install_skills_to_targets, mcp_registration_lines
from .common import load_json_object
from .hooks_patch import patch_nested_hook_events
from .instructions import apply_project_instructions
from .tomlcfg import mcp_registered_toml, remove_codex_mcp, upsert_codex_mcp
from .types import HostResult

_HOOK_EVENTS = (
    ("PreToolUse", "pre-tool-use", "Bash"),
    ("PostToolUse", "post-tool-use", "apply_patch|Edit|Write"),
    ("SessionStart", "session-start", None),
)


class CodexHost(HostInstaller):
    name = "codex"
    title = "Codex"
    events = ("pre-tool-use", "post-tool-use", "session-start")

    def _config_file(self, root: Path, *, global_config: bool, home: Path) -> Path:
        if global_config:
            return home / ".codex" / "config.toml"
        return root / ".codex" / "config.toml"

    def _hooks_file(self, root: Path, *, global_config: bool, home: Path) -> Path:
        if global_config:
            return home / ".codex" / "hooks.json"
        return root / ".codex" / "hooks.json"

    def install(self, root: Path, *, global_config: bool, home: Path) -> HostResult:
        cfg = self._config_file(root, global_config=global_config, home=home)
        upsert_codex_mcp(cfg)
        label = str(cfg) if global_config else ".codex/config.toml"
        lines = mcp_registration_lines(label)

        hooks_path = self._hooks_file(root, global_config=global_config, home=home)
        patch_nested_hook_events(hooks_path, self.name, _HOOK_EVENTS)
        lines.append(f"hooks registered in {hooks_path}")
        lines.append("PreToolUse Bash: cat/head/rg/grep of indexed files → hc_*")
        lines.append("PostToolUse apply_patch|Edit|Write → hc update")
        lines.append("SessionStart: incremental hc update + hc_* reminder")
        lines.extend(apply_project_instructions(root=root, host=self.name))

        targets = [(home / ".agents" / "skills", home / ".agents" / "skills")]
        if not global_config:
            targets.append((root / ".agents" / "skills", Path(".agents/skills")))
        skills, skill_lines = install_skills_to_targets(targets, self.name)
        lines.extend(skill_lines)
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
