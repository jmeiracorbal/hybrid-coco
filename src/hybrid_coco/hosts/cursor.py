"""Cursor host: project .cursor/mcp.json, hooks.json, and equivalent skills."""

from __future__ import annotations

from pathlib import Path

from .base import JsonMcpHostInstaller
from .hooks_patch import patch_flat_hook_events
from .common import load_json_object
from .types import HostResult

_HOOK_EVENTS = (
    ("preToolUse", "pre-tool-use", "Read|Grep"),
    ("beforeReadFile", "before-read-file", None),
    ("postToolUse", "post-tool-use", "Write|StrReplace"),
    ("afterFileEdit", "after-file-edit", None),
    ("sessionStart", "session-start", None),
)


class CursorHost(JsonMcpHostInstaller):
    name = "cursor"
    title = "Cursor"
    events = (
        "pre-tool-use",
        "post-tool-use",
        "before-read-file",
        "after-file-edit",
        "session-start",
    )
    project_mcp_rel = Path(".cursor") / "mcp.json"
    global_mcp_rel = Path(".cursor") / "mcp.json"
    project_mcp_label = ".cursor/mcp.json"

    def _hooks_path(self, root: Path, *, global_config: bool, home: Path) -> Path:
        if global_config:
            return home / ".cursor" / "hooks.json"
        return root / ".cursor" / "hooks.json"

    def install(self, root: Path, *, global_config: bool, home: Path) -> HostResult:
        lines = self.register_mcp(root, global_config=global_config, home=home)

        hooks_path = self._hooks_path(root, global_config=global_config, home=home)
        patch_flat_hook_events(hooks_path, self.name, _HOOK_EVENTS)
        lines.append(f"hooks registered in {hooks_path}")
        lines.append("preToolUse/beforeReadFile: Read|Grep → hc_* suggestion")
        lines.append("postToolUse/afterFileEdit: Write|StrReplace → hc update")
        lines.append("sessionStart: incremental hc update when an index exists")
        lines.extend(self._apply_project(root))

        skills, skill_lines = self.install_skills(
            root,
            global_config=global_config,
            home=home,
            home_skills=home / ".cursor" / "skills",
            project_skills=root / ".cursor" / "skills",
            project_label=Path(".cursor/skills"),
        )
        lines.extend(skill_lines)
        return HostResult(name=self.name, title=self.title, lines=lines, skills=skills)

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
