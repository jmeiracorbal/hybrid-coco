"""tests for agent host installers and lifecycle hooks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from hybrid_coco.cli import main
from hybrid_coco.hosts import HOST_NAMES, resolve_host_names
from hybrid_coco.hosts.common import SKILL_NAMES, skills_src
from hybrid_coco.hosts.claude import ClaudeHost
from hybrid_coco.hosts.codex import CodexHost
from hybrid_coco.hosts.cursor import CursorHost
from hybrid_coco.hosts.devin import DevinHost
from hybrid_coco.hosts.opencode import OpenCodeHost
from hybrid_coco.hosts.marker import add_agent, marker_path, project_id_from_path
from hybrid_coco.indexer import index_path


def _out(result) -> str:
    return result.output + (result.stderr or "")


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    src = tmp_path / "proj" / "src"
    src.mkdir(parents=True)
    (src / "sample.py").write_text(
        "def greet(name: str) -> str:\n    '''Say hello.'''\n    return name\n"
    )
    return tmp_path / "proj"


def _home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


def _index_and_activate(project: Path) -> None:
    index_path(project)
    add_agent(project, "claude")


def _assert_no_project_instruction_files(root: Path) -> None:
    assert not (root / "AGENTS.md").exists()
    assert not (root / "CLAUDE.md").exists()
    assert not (root / ".cursor" / "rules" / "hybrid-coco.mdc").exists()


def _assert_no_global_instruction_files(home: Path) -> None:
    assert not (home / ".claude" / "CLAUDE.md").exists()
    assert not (home / ".cursor" / "rules" / "hybrid-coco.mdc").exists()
    assert not (home / ".codex" / "AGENTS.md").exists()
    assert not (home / ".config" / "opencode" / "AGENTS.md").exists()
    assert not (home / ".config" / "devin" / "AGENTS.md").exists()


def _assert_skills_match_host(dest: Path, host: str) -> None:
    src = skills_src(host)
    for name in SKILL_NAMES:
        got = dest / name / "SKILL.md"
        expected = src / name / "SKILL.md"
        assert got.is_file()
        assert got.read_bytes() == expected.read_bytes()
        refs = src / name / "references"
        if refs.is_dir():
            for ref in refs.iterdir():
                assert (dest / name / "references" / ref.name).read_bytes() == ref.read_bytes()


def test_resolve_host_names_rejects_unknown():
    with pytest.raises(ValueError, match="unknown host"):
        resolve_host_names(("nope",))


def test_resolve_host_names_all_is_exclusive():
    with pytest.raises(ValueError, match="cannot be combined"):
        resolve_host_names(("all", "cursor"))
    assert resolve_host_names(("all",)) == HOST_NAMES


def test_claude_install_writes_skills_and_mcp(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "proj"
    root.mkdir()
    result = ClaudeHost().install(root, global_config=False, home=home)
    assert set(result.skills) == set(SKILL_NAMES)
    settings = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings["mcpServers"]["hybrid-coco"]["command"] == "hc"
    for dest in (home / ".claude" / "skills",):
        _assert_skills_match_host(dest, "claude")
    assert (home / ".claude" / "hooks" / "hc-pre-tool-use.sh").is_file()
    global_settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    matchers = [e["matcher"] for e in global_settings["hooks"]["PreToolUse"]]
    assert "Read|Grep" in matchers
    assert not (home / ".claude" / "CLAUDE.md").exists()
    assert not (home / ".claude" / "hybrid-coco.md").exists()
    _assert_no_project_instruction_files(root)
    awareness = (root / ".hybrid-coco" / "hybrid-coco.md").read_text(encoding="utf-8")
    assert "hc_file_context" in awareness
    marker = json.loads((root / ".hybrid-coco" / "project.json").read_text(encoding="utf-8"))
    assert marker["agents"] == ["claude"]
    assert marker["id"] == project_id_from_path(root.resolve())


def test_claude_install_does_not_touch_global_claude_md(tmp_path: Path):
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "hybrid-coco.md").write_text("stale\n", encoding="utf-8")
    (claude_dir / "CLAUDE.md").write_text("User notes\n@hybrid-coco.md\n", encoding="utf-8")
    root = tmp_path / "proj"
    root.mkdir()
    ClaudeHost().install(root, global_config=False, home=home)
    assert (claude_dir / "hybrid-coco.md").is_file()
    leftover = (claude_dir / "CLAUDE.md").read_text(encoding="utf-8")
    assert leftover == "User notes\n@hybrid-coco.md\n"
    _assert_no_project_instruction_files(root)


def test_cursor_install_matches_packaged_skills(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "proj"
    root.mkdir()
    result = CursorHost().install(root, global_config=False, home=home)
    assert set(result.skills) == set(SKILL_NAMES)

    mcp = json.loads((root / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert mcp["mcpServers"]["hybrid-coco"]["args"] == ["serve"]
    assert mcp["mcpServers"]["hybrid-coco"]["type"] == "stdio"

    hooks = json.loads((root / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert hooks["version"] == 1
    pre = hooks["hooks"]["preToolUse"]
    assert any(e["command"] == "hc hook cursor pre-tool-use" for e in pre)
    assert any(e.get("matcher") == "Read|Grep" for e in pre)
    assert any(
        e["command"] == "hc hook cursor before-read-file"
        for e in hooks["hooks"]["beforeReadFile"]
    )
    assert any(
        e["command"] == "hc hook cursor after-file-edit"
        for e in hooks["hooks"]["afterFileEdit"]
    )

    for dest in (home / ".cursor" / "skills", root / ".cursor" / "skills"):
        _assert_skills_match_host(dest, "cursor")
    assert not (home / ".cursor" / "rules" / "hybrid-coco.mdc").exists()
    _assert_no_project_instruction_files(root)

    # idempotent
    CursorHost().install(root, global_config=False, home=home)
    hooks2 = json.loads((root / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    commands = [e["command"] for e in hooks2["hooks"]["preToolUse"]]
    assert commands.count("hc hook cursor pre-tool-use") == 1


def test_cursor_preserves_other_mcp_servers(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "proj"
    cursor = root / ".cursor"
    cursor.mkdir(parents=True)
    (cursor / "mcp.json").write_text(
        '{"mcpServers": {"other": {"command": "x"}}}\n',
        encoding="utf-8",
    )
    CursorHost().install(root, global_config=False, home=home)
    data = json.loads((cursor / "mcp.json").read_text(encoding="utf-8"))
    assert data["mcpServers"]["other"]["command"] == "x"
    assert data["mcpServers"]["hybrid-coco"]["command"] == "hc"


def test_init_host_cursor(project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = _home(monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(project), "--host", "cursor"])
    assert result.exit_code == 0, result.output
    assert "Cursor integration" in result.output
    assert (project / ".cursor" / "mcp.json").is_file()
    assert not (project / ".claude" / "settings.json").exists()
    assert (home / ".cursor" / "skills" / "hybrid-coco" / "SKILL.md").is_file()
    assert not (home / ".cursor" / "rules" / "hybrid-coco.mdc").exists()
    _assert_no_project_instruction_files(project)


def test_init_default_is_claude_only(project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _home(monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(project)])
    assert result.exit_code == 0, result.output
    assert (project / ".claude" / "settings.json").is_file()
    assert not (project / ".cursor" / "mcp.json").exists()
    _assert_no_project_instruction_files(project)
    home = tmp_path / "home"
    _assert_no_global_instruction_files(home)
    marker = json.loads((project / ".hybrid-coco" / "project.json").read_text(encoding="utf-8"))
    assert marker["id"]
    assert marker["agents"] == ["claude"]


def test_init_host_all(project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _home(monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(project), "--host", "all"])
    assert result.exit_code == 0, result.output
    assert (project / ".claude" / "settings.json").is_file()
    assert (project / ".cursor" / "mcp.json").is_file()
    assert (project / ".codex" / "config.toml").is_file()
    assert (project / "opencode.json").is_file()
    assert (project / ".devin" / "mcp_config.json").is_file()
    _assert_no_project_instruction_files(project)
    marker = json.loads((project / ".hybrid-coco" / "project.json").read_text(encoding="utf-8"))
    assert set(marker["agents"]) == {"claude", "cursor", "codex", "opencode", "devin"}
    assert marker["id"]
    _assert_no_global_instruction_files(tmp_path / "home")


def test_init_unknown_host_fails(project: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(project), "--host", "nope"])
    assert result.exit_code == 1
    assert "unknown host" in _out(result)


def test_hook_does_not_block_without_marker(project: Path, monkeypatch: pytest.MonkeyPatch):
    index_path(project)
    monkeypatch.chdir(project)
    payload = json.dumps({
        "tool_name": "Read",
        "tool_input": {"path": str(project / "src" / "sample.py")},
    })
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "cursor", "pre-tool-use"], input=payload)
    assert result.exit_code == 0, result.output
    assert result.output.strip() == ""


def test_hook_repairs_invalid_id_then_blocks(project: Path, monkeypatch: pytest.MonkeyPatch):
    index_path(project)
    path = marker_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "id": "not-a-uuid", "agents": ["claude"]}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(project)
    payload = json.dumps({
        "tool_name": "Read",
        "tool_input": {"path": str(project / "src" / "sample.py")},
    })
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "cursor", "pre-tool-use"], input=payload)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["permission"] == "deny"
    marker = json.loads(path.read_text(encoding="utf-8"))
    assert marker["id"] == project_id_from_path(project.resolve())
    assert marker["agents"] == ["claude"]


def test_cursor_hook_blocks_read(project: Path, monkeypatch: pytest.MonkeyPatch):
    _index_and_activate(project)
    monkeypatch.chdir(project)
    payload = json.dumps({
        "tool_name": "Read",
        "tool_input": {"path": str(project / "src" / "sample.py")},
    })
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "cursor", "pre-tool-use"], input=payload)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["permission"] == "deny"
    assert "hc_file_context" in data["agent_message"]
    assert "greet" in data["agent_message"]


def test_cursor_hook_blocks_grep(project: Path, monkeypatch: pytest.MonkeyPatch):
    _index_and_activate(project)
    monkeypatch.chdir(project)
    payload = json.dumps({
        "tool_name": "Grep",
        "tool_input": {"pattern": "greet"},
    })
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "cursor", "pre-tool-use"], input=payload)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["permission"] == "deny"
    assert "hc_search" in data["agent_message"]
    assert "greet" in data["agent_message"]


def test_cursor_before_read_file(project: Path, monkeypatch: pytest.MonkeyPatch):
    _index_and_activate(project)
    monkeypatch.chdir(project)
    payload = json.dumps({"file_path": str(project / "src" / "sample.py")})
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "cursor", "before-read-file"], input=payload)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["permission"] == "deny"
    assert "Symbols for" in data["agent_message"]


def test_cursor_hook_passes_unindexed_file(project: Path, monkeypatch: pytest.MonkeyPatch):
    _index_and_activate(project)
    monkeypatch.chdir(project)
    payload = json.dumps({
        "tool_name": "Read",
        "tool_input": {"path": str(project / "README.md")},
    })
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "cursor", "pre-tool-use"], input=payload)
    assert result.exit_code == 0, result.output
    assert result.output.strip() == ""


def test_claude_hook_block_shape(project: Path, monkeypatch: pytest.MonkeyPatch):
    _index_and_activate(project)
    monkeypatch.chdir(project)
    payload = json.dumps({
        "tool_name": "Read",
        "tool_input": {"file_path": str(project / "src" / "sample.py")},
    })
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "claude", "pre-tool-use"], input=payload)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["decision"] == "block"
    assert "reason" in data


def test_hook_unknown_host_fails():
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "nope", "pre-tool-use"], input="{}")
    assert result.exit_code == 1
    assert "unknown host" in _out(result)


def test_reset_all_removes_cursor_mcp(project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _home(monkeypatch, tmp_path)
    _index_and_activate(project)
    CursorHost().install(project, global_config=False, home=tmp_path / "home")
    settings = project / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        '{"mcpServers": {"hybrid-coco": {"command": "hc"}, "other": {"command": "x"}}}\n',
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["reset", str(project), "-f", "--all"])
    assert result.exit_code == 0, result.output
    claude = json.loads(settings.read_text(encoding="utf-8"))
    assert "hybrid-coco" not in claude["mcpServers"]
    assert "other" in claude["mcpServers"]
    cursor = json.loads((project / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert "hybrid-coco" not in cursor["mcpServers"]


def test_codex_install_writes_toml_hooks_skills(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".codex").mkdir()
    (root / ".codex" / "config.toml").write_text(
        '[mcp_servers.other]\ncommand = "x"\n',
        encoding="utf-8",
    )
    result = CodexHost().install(root, global_config=False, home=home)
    assert set(result.skills) == set(SKILL_NAMES)
    text = (root / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert 'command = "x"' in text
    assert "[mcp_servers.hybrid-coco]" in text
    hooks = json.loads((root / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    pre = hooks["hooks"]["PreToolUse"]
    assert any(e.get("matcher") == "Bash" for e in pre)
    assert any(
        any(h.get("command") == "hc hook codex pre-tool-use" for h in e.get("hooks", []))
        for e in pre
    )
    for dest in (home / ".agents" / "skills", root / ".agents" / "skills"):
        _assert_skills_match_host(dest, "codex")
    assert not (home / ".codex" / "AGENTS.md").exists()
    _assert_no_project_instruction_files(root)
    CodexHost().install(root, global_config=False, home=home)
    hooks2 = json.loads((root / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    commands = [
        h.get("command")
        for e in hooks2["hooks"]["PreToolUse"]
        for h in e.get("hooks", [])
    ]
    assert commands.count("hc hook codex pre-tool-use") == 1


def test_init_host_codex(project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _home(monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(project), "--host", "codex"])
    assert result.exit_code == 0, result.output
    assert "Codex integration" in result.output
    assert (project / ".codex" / "config.toml").is_file()
    assert not (project / ".cursor" / "mcp.json").exists()


def test_codex_hook_blocks_bash_cat(project: Path, monkeypatch: pytest.MonkeyPatch):
    _index_and_activate(project)
    monkeypatch.chdir(project)
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": f"cat {project / 'src' / 'sample.py'}"},
    })
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "codex", "pre-tool-use"], input=payload)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["decision"] == "block"
    assert "hc_file_context" in data["reason"]
    assert "greet" in data["reason"]


def test_codex_session_start_injects_context(project: Path, monkeypatch: pytest.MonkeyPatch):
    _index_and_activate(project)
    monkeypatch.chdir(project)
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "codex", "session-start"], input="{}")
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "hc_*" in data["hookSpecificOutput"]["additionalContext"]


def test_opencode_install_plugin_mcp_skills(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "proj"
    root.mkdir()
    (root / "opencode.json").write_text(
        '{"mcp": {"other": {"type": "local", "command": ["x"]}}}\n',
        encoding="utf-8",
    )
    result = OpenCodeHost().install(root, global_config=False, home=home)
    assert set(result.skills) == set(SKILL_NAMES)
    data = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
    assert data["mcp"]["other"]["command"] == ["x"]
    assert data["mcp"]["hybrid-coco"]["command"] == ["hc", "serve"]
    assert data["mcp"]["hybrid-coco"]["type"] == "local"
    plugin = (root / ".opencode" / "plugins" / "hybrid-coco.js").read_text(encoding="utf-8")
    assert "tool.execute.before" in plugin
    assert '"hook", "opencode"' in plugin
    for dest in (
        home / ".config" / "opencode" / "skills",
        root / ".opencode" / "skills",
    ):
        _assert_skills_match_host(dest, "opencode")
    assert not (home / ".config" / "opencode" / "AGENTS.md").exists()
    _assert_no_project_instruction_files(root)


def test_init_host_opencode(project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _home(monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(project), "--host", "opencode"])
    assert result.exit_code == 0, result.output
    assert "OpenCode integration" in result.output
    assert (project / "opencode.json").is_file()
    assert not (project / ".cursor" / "mcp.json").exists()


def test_opencode_hook_blocks_read_filepath(project: Path, monkeypatch: pytest.MonkeyPatch):
    _index_and_activate(project)
    monkeypatch.chdir(project)
    payload = json.dumps({
        "tool_name": "read",
        "tool_input": {"filePath": str(project / "src" / "sample.py")},
    })
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "opencode", "pre-tool-use"], input=payload)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["block"] is True
    assert "hc_file_context" in data["reason"]
    assert "greet" in data["reason"]


def test_opencode_hook_ignores_claude_file_path_key(project: Path, monkeypatch: pytest.MonkeyPatch):
    _index_and_activate(project)
    monkeypatch.chdir(project)
    payload = json.dumps({
        "tool_name": "read",
        "tool_input": {"file_path": str(project / "src" / "sample.py")},
    })
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "opencode", "pre-tool-use"], input=payload)
    assert result.exit_code == 0, result.output
    assert result.output.strip() == ""


def test_devin_install_mcp_hooks_skills(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "proj"
    root.mkdir()
    result = DevinHost().install(root, global_config=False, home=home)
    assert set(result.skills) == set(SKILL_NAMES)
    mcp = json.loads((root / ".devin" / "mcp_config.json").read_text(encoding="utf-8"))
    assert mcp["mcpServers"]["hybrid-coco"]["command"] == "hc"
    hooks = json.loads((root / ".devin" / "hooks.v1.json").read_text(encoding="utf-8"))
    assert "hooks" not in hooks
    pre = hooks["PreToolUse"]
    assert any(e.get("matcher") == "^(read|grep)$" for e in pre)
    assert any(
        any(h.get("command") == "hc hook devin pre-tool-use" for h in e.get("hooks", []))
        for e in pre
    )
    for dest in (home / ".config" / "devin" / "skills", root / ".devin" / "skills"):
        _assert_skills_match_host(dest, "devin")
    assert not (home / ".config" / "devin" / "AGENTS.md").exists()
    _assert_no_project_instruction_files(root)
    DevinHost().install(root, global_config=False, home=home)
    hooks2 = json.loads((root / ".devin" / "hooks.v1.json").read_text(encoding="utf-8"))
    commands = [
        h.get("command")
        for e in hooks2["PreToolUse"]
        for h in e.get("hooks", [])
    ]
    assert commands.count("hc hook devin pre-tool-use") == 1


def test_init_host_devin(project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _home(monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(project), "--host", "devin"])
    assert result.exit_code == 0, result.output
    assert "Devin integration" in result.output
    assert (project / ".devin" / "mcp_config.json").is_file()
    assert not (project / ".cursor" / "mcp.json").exists()


def test_devin_hook_blocks_lowercase_read(project: Path, monkeypatch: pytest.MonkeyPatch):
    _index_and_activate(project)
    monkeypatch.chdir(project)
    payload = json.dumps({
        "tool_name": "read",
        "tool_input": {"file_path": str(project / "src" / "sample.py")},
    })
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "devin", "pre-tool-use"], input=payload)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["decision"] == "block"
    assert "hc_file_context" in data["reason"]
    assert "greet" in data["reason"]


def test_devin_hook_blocks_grep(project: Path, monkeypatch: pytest.MonkeyPatch):
    _index_and_activate(project)
    monkeypatch.chdir(project)
    payload = json.dumps({
        "tool_name": "grep",
        "tool_input": {"pattern": "greet"},
    })
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "devin", "pre-tool-use"], input=payload)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["decision"] == "block"
    assert "hc_search" in data["reason"]


def test_skills_src_rejects_unknown_host():
    with pytest.raises(ValueError, match="unknown host"):
        skills_src("nope")


def test_host_skills_are_adapted_not_copied():
    claude = skills_src("claude") / "hybrid-coco" / "SKILL.md"
    claude_text = claude.read_text(encoding="utf-8")
    assert ".claude/settings.json" in claude_text
    assert "Claude Code" in claude_text
    for name in SKILL_NAMES:
        text = (skills_src("claude") / name / "SKILL.md").read_text(encoding="utf-8")
        assert "hc_inspect" not in text
        assert "hc_map" not in text

    cursor = (skills_src("cursor") / "hybrid-coco" / "SKILL.md").read_text(encoding="utf-8")
    assert cursor != claude_text
    assert ".cursor/mcp.json" in cursor
    assert "beforeReadFile" in cursor
    assert "permission" in cursor or "deny" in cursor

    codex = (skills_src("codex") / "hybrid-coco" / "SKILL.md").read_text(encoding="utf-8")
    assert ".codex/config.toml" in codex
    assert "apply_patch" in codex
    assert "Bash" in codex
    assert "hc_file_context" in codex
    assert "hc_inspect" not in codex

    opencode = (skills_src("opencode") / "hybrid-coco" / "SKILL.md").read_text(encoding="utf-8")
    assert "opencode.json" in opencode
    assert "filePath" in opencode
    assert "file_path" in opencode
    assert "plugin" in opencode.lower() or "hybrid-coco.js" in opencode

    devin = (skills_src("devin") / "hybrid-coco" / "SKILL.md").read_text(encoding="utf-8")
    assert ".devin/mcp_config.json" in devin
    assert "hooks.v1.json" in devin
    assert "file_path" in devin
    assert "lowercase" in devin.lower()
