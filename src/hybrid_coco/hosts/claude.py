"""Claude Code host: MCP in .claude/settings.json, hooks and skills under ~/.claude."""

from __future__ import annotations

from pathlib import Path

from .base import JsonMcpHostInstaller, install_skills_to_targets
from .common import copy_hook_scripts, load_json_object, remove_mcp_json, write_json
from .hooks_patch import hook_command_present
from .types import HostResult

_HOOK_NAMES = ("hc-pre-tool-use.sh", "hc-post-tool-use.sh")
_HC_HOOK_PATH_PRE = "~/.claude/hooks/hc-pre-tool-use.sh"
_HC_HOOK_PATH_POST = "~/.claude/hooks/hc-post-tool-use.sh"
_HC_PRE_HOOK_ENTRY = {
    "matcher": "Read|Grep",
    "hooks": [{"type": "command", "command": _HC_HOOK_PATH_PRE}],
}
_HC_POST_HOOK_ENTRY = {
    "matcher": "Write|Edit",
    "hooks": [{"type": "command", "command": _HC_HOOK_PATH_POST}],
}


def _patch_claude_hooks(settings_path: Path) -> bool:
    data = load_json_object(settings_path) if settings_path.is_file() else {}
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    pre = hooks.get("PreToolUse")
    if not isinstance(pre, list):
        pre = []
        hooks["PreToolUse"] = pre
    post = hooks.get("PostToolUse")
    if not isinstance(post, list):
        post = []
        hooks["PostToolUse"] = post

    patched = False
    if not hook_command_present(pre, _HC_HOOK_PATH_PRE):
        pre.append(_HC_PRE_HOOK_ENTRY)
        patched = True
    if not hook_command_present(post, _HC_HOOK_PATH_POST):
        post.append(_HC_POST_HOOK_ENTRY)
        patched = True

    write_json(settings_path, data)
    return patched


class ClaudeHost(JsonMcpHostInstaller):
    name = "claude"
    title = "Claude Code"
    events = ("pre-tool-use", "post-tool-use", "session-start")
    project_mcp_rel = Path(".claude") / "settings.json"
    global_mcp_rel = Path(".claude") / "settings.json"
    project_mcp_label = ".claude/settings.json"

    def install(self, root: Path, *, global_config: bool, home: Path) -> HostResult:
        lines = self.register_mcp(root, global_config=global_config, home=home)

        claude_dir = home / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        lines.extend(self._apply_project(root))

        copy_hook_scripts(claude_dir / "hooks", _HOOK_NAMES)
        lines.append("hooks installed in ~/.claude/hooks/")
        lines.append("PreToolUse: Read|Grep → hc_* suggestion")
        lines.append("PostToolUse: Write|Edit → hc update")

        skills, skill_lines = install_skills_to_targets(
            [(claude_dir / "skills", "~/.claude/skills/")],
            self.name,
        )
        lines.extend(skill_lines)

        _patch_claude_hooks(claude_dir / "settings.json")
        return HostResult(name=self.name, title=self.title, lines=lines, skills=skills)

    def hooks_present(self, root: Path, *, home: Path) -> bool:
        hooks_dir = home / ".claude" / "hooks"
        return all((hooks_dir / name).is_file() for name in _HOOK_NAMES)

    def remove_mcp(self, root: Path, *, home: Path) -> list[str]:
        actions: list[str] = []
        for path in (root / ".claude" / "settings.json",):
            msg = remove_mcp_json(path)
            if msg is None:
                actions.append(f"no hybrid-coco MCP entry in {path}")
            else:
                actions.append(msg)
        return actions
