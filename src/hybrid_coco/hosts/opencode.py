"""OpenCode host: MCP in opencode.json, skills under .opencode, JS plugin hooks."""

from __future__ import annotations

from pathlib import Path

from .base import HostInstaller, install_skills_to_targets, mcp_registration_lines
from .common import ASSETS_DIR, load_json_object, write_json
from .instructions import apply_project_instructions
from .types import HostResult

_MCP_ENTRY = {
    "type": "local",
    "command": ["hc", "serve"],
    "enabled": True,
}
_PLUGIN_NAME = "hybrid-coco.js"


def _config_file(root: Path, *, global_config: bool, home: Path) -> Path:
    if global_config:
        return home / ".config" / "opencode" / "opencode.json"
    return root / "opencode.json"


def _plugin_file(root: Path, *, global_config: bool, home: Path) -> Path:
    if global_config:
        return home / ".config" / "opencode" / "plugins" / _PLUGIN_NAME
    return root / ".opencode" / "plugins" / _PLUGIN_NAME


def _merge_mcp(path: Path) -> None:
    if path.is_file():
        data = load_json_object(path)
    else:
        data = {"$schema": "https://opencode.ai/config.json"}
    mcp = data.get("mcp")
    if mcp is None:
        mcp = {}
        data["mcp"] = mcp
    if not isinstance(mcp, dict):
        raise ValueError(f"{path}: mcp must be an object")
    mcp["hybrid-coco"] = dict(_MCP_ENTRY)
    write_json(path, data)


def _remove_mcp(path: Path) -> str | None:
    if not path.is_file():
        return None
    data = load_json_object(path)
    mcp = data.get("mcp")
    if not isinstance(mcp, dict) or "hybrid-coco" not in mcp:
        return None
    del mcp["hybrid-coco"]
    write_json(path, data)
    return f"removed hybrid-coco MCP entry from {path}"


def _install_plugin(dst: Path) -> None:
    src = ASSETS_DIR / "hosts" / "opencode" / "plugin.js"
    if not src.is_file():
        raise FileNotFoundError(f"packaged OpenCode plugin missing: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


class OpenCodeHost(HostInstaller):
    name = "opencode"
    title = "OpenCode"
    events = ("pre-tool-use", "post-tool-use")

    def install(self, root: Path, *, global_config: bool, home: Path) -> HostResult:
        cfg = _config_file(root, global_config=global_config, home=home)
        _merge_mcp(cfg)
        label = str(cfg) if global_config else "opencode.json"
        lines = mcp_registration_lines(label)

        plugin = _plugin_file(root, global_config=global_config, home=home)
        _install_plugin(plugin)
        lines.append(f"plugin installed at {plugin}")
        lines.append("tool.execute.before: read/grep → hc_*")
        lines.append("tool.execute.after: write/edit → hc update")
        lines.extend(apply_project_instructions(root=root, host=self.name))

        targets = [(home / ".config" / "opencode" / "skills", home / ".config" / "opencode" / "skills")]
        if not global_config:
            targets.append((root / ".opencode" / "skills", Path(".opencode/skills")))
        skills, skill_lines = install_skills_to_targets(targets, self.name)
        lines.extend(skill_lines)
        return HostResult(name=self.name, title=self.title, lines=lines, skills=skills)

    def mcp_registered(self, root: Path, *, home: Path) -> bool:
        for path in (
            root / "opencode.json",
            home / ".config" / "opencode" / "opencode.json",
        ):
            if not path.is_file():
                continue
            try:
                data = load_json_object(path)
            except ValueError:
                continue
            mcp = data.get("mcp")
            if isinstance(mcp, dict) and "hybrid-coco" in mcp:
                return True
        return False

    def hooks_present(self, root: Path, *, home: Path) -> bool:
        return _plugin_file(root, global_config=False, home=home).is_file() or _plugin_file(
            root, global_config=True, home=home
        ).is_file()

    def mcp_locations(self, root: Path, *, home: Path) -> list[Path]:
        return [
            root / "opencode.json",
            home / ".config" / "opencode" / "opencode.json",
        ]

    def remove_mcp(self, root: Path, *, home: Path) -> list[str]:
        path = root / "opencode.json"
        msg = _remove_mcp(path)
        if msg is None:
            return [f"no hybrid-coco MCP entry in {path}"]
        return [msg]
