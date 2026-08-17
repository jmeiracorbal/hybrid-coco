"""Claude Code host: MCP in .claude/settings.json, hooks and skills under ~/.claude."""

from __future__ import annotations

from pathlib import Path

from .common import (
    ASSETS_DIR,
    MCP_TOOLS,
    copy_hook_scripts,
    copy_skills,
    skills_src,
    load_json_object,
    mcp_registered_json,
    merge_mcp_json,
    remove_mcp_json,
    write_json,
)
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


def _entry_present(entries: list, command: str) -> bool:
    for entry in entries:
        for hook in entry.get("hooks", []):
            if hook.get("command") == command:
                return True
    return False


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
    if not _entry_present(pre, _HC_HOOK_PATH_PRE):
        pre.append(_HC_PRE_HOOK_ENTRY)
        patched = True
    if not _entry_present(post, _HC_HOOK_PATH_POST):
        post.append(_HC_POST_HOOK_ENTRY)
        patched = True

    write_json(settings_path, data)
    return patched


class ClaudeHost:
    name = "claude"
    title = "Claude Code"
    events = ("pre-tool-use", "post-tool-use", "session-start")

    def install(self, root: Path, *, global_config: bool, home: Path) -> HostResult:
        lines: list[str] = []
        claude_dir = home / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)

        if global_config:
            mcp_settings = claude_dir / "settings.json"
            mcp_label = str(mcp_settings)
        else:
            mcp_settings = root / ".claude" / "settings.json"
            mcp_label = ".claude/settings.json"
        merge_mcp_json(mcp_settings)
        lines.append(f"MCP server registered in {mcp_label}")
        for tool in MCP_TOOLS:
            lines.append(tool)

        src_awareness = ASSETS_DIR / "hybrid-coco.md"
        if not src_awareness.is_file():
            raise FileNotFoundError(f"packaged awareness missing: {src_awareness}")
        dst_awareness = claude_dir / "hybrid-coco.md"
        dst_awareness.write_text(src_awareness.read_text(encoding="utf-8"), encoding="utf-8")
        lines.append("~/.claude/hybrid-coco.md written")

        claude_md = claude_dir / "CLAUDE.md"
        tag = "@hybrid-coco.md"
        if claude_md.exists():
            content = claude_md.read_text(encoding="utf-8")
        else:
            content = ""
        if tag not in content:
            sep = "\n" if content and not content.endswith("\n") else ""
            claude_md.write_text(content + sep + tag + "\n", encoding="utf-8")
            lines.append("@hybrid-coco.md added to ~/.claude/CLAUDE.md")
        else:
            lines.append("@hybrid-coco.md already in ~/.claude/CLAUDE.md")

        copy_hook_scripts(claude_dir / "hooks", _HOOK_NAMES)
        lines.append("hooks installed in ~/.claude/hooks/")
        lines.append("PreToolUse: Read|Grep → hc_* suggestion")
        lines.append("PostToolUse: Write|Edit → hc update")

        skills = copy_skills(claude_dir / "skills", skills_src(self.name))
        lines.append(f"skills installed in ~/.claude/skills/: {', '.join(skills)}")

        _patch_claude_hooks(claude_dir / "settings.json")
        return HostResult(name=self.name, title=self.title, lines=lines, skills=skills)

    def mcp_registered(self, root: Path, *, home: Path) -> bool:
        project = root / ".claude" / "settings.json"
        global_settings = home / ".claude" / "settings.json"
        return mcp_registered_json(project) or mcp_registered_json(global_settings)

    def hooks_present(self, root: Path, *, home: Path) -> bool:
        hooks_dir = home / ".claude" / "hooks"
        return all((hooks_dir / name).is_file() for name in _HOOK_NAMES)

    def mcp_locations(self, root: Path, *, home: Path) -> list[Path]:
        return [root / ".claude" / "settings.json", home / ".claude" / "settings.json"]

    def remove_mcp(self, root: Path, *, home: Path) -> list[str]:
        actions: list[str] = []
        for path in (root / ".claude" / "settings.json",):
            msg = remove_mcp_json(path)
            if msg is None:
                actions.append(f"no hybrid-coco MCP entry in {path}")
            else:
                actions.append(msg)
        return actions
