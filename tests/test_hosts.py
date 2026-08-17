"""tests for agent host installers and lifecycle hooks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from hybrid_coco.cli import main
from hybrid_coco.hosts import HOST_NAMES, resolve_host_names
from hybrid_coco.hosts.common import SKILL_NAMES
from hybrid_coco.hosts.claude import ClaudeHost
from hybrid_coco.hosts.cursor import CursorHost
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
    for name in SKILL_NAMES:
        skill_md = home / ".claude" / "skills" / name / "SKILL.md"
        assert skill_md.is_file()
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---")
        assert f"name: {name}" in text
    assert (home / ".claude" / "hooks" / "hc-pre-tool-use.sh").is_file()
    global_settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    matchers = [e["matcher"] for e in global_settings["hooks"]["PreToolUse"]]
    assert "Read|Grep" in matchers


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

    packaged = Path(__file__).resolve().parents[1] / "src" / "hybrid_coco" / "assets" / "skills"
    for dest in (home / ".cursor" / "skills", root / ".cursor" / "skills"):
        for name in SKILL_NAMES:
            got = (dest / name / "SKILL.md").read_text(encoding="utf-8")
            expected = (packaged / name / "SKILL.md").read_text(encoding="utf-8")
            assert got == expected
            assert (dest / name / "SKILL.md").read_bytes() == (
                packaged / name / "SKILL.md"
            ).read_bytes()

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


def test_init_default_is_claude_only(project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _home(monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(project)])
    assert result.exit_code == 0, result.output
    assert (project / ".claude" / "settings.json").is_file()
    assert not (project / ".cursor" / "mcp.json").exists()


def test_init_host_all(project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _home(monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(project), "--host", "all"])
    assert result.exit_code == 0, result.output
    assert (project / ".claude" / "settings.json").is_file()
    assert (project / ".cursor" / "mcp.json").is_file()


def test_init_unknown_host_fails(project: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(project), "--host", "nope"])
    assert result.exit_code == 1
    assert "unknown host" in _out(result)


def test_cursor_hook_blocks_read(project: Path, monkeypatch: pytest.MonkeyPatch):
    index_path(project)
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
    index_path(project)
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
    index_path(project)
    monkeypatch.chdir(project)
    payload = json.dumps({"file_path": str(project / "src" / "sample.py")})
    runner = CliRunner()
    result = runner.invoke(main, ["hook", "cursor", "before-read-file"], input=payload)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["permission"] == "deny"
    assert "Symbols for" in data["agent_message"]


def test_cursor_hook_passes_unindexed_file(project: Path, monkeypatch: pytest.MonkeyPatch):
    index_path(project)
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
    index_path(project)
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
    index_path(project)
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
