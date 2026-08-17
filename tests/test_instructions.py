"""tests for mnemo-style global instruction install and project marker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from hybrid_coco.cli import main
from hybrid_coco.hosts.instructions import (
    AWARENESS_REL,
    CURSOR_GLOBAL_RULE,
    GLOBAL_BODY,
    SECTION_END,
    SECTION_START,
    apply_project_instructions,
    install_global_instructions,
    strip_legacy_global_claude_include,
    upsert_managed_section,
    write_project_awareness,
)
from hybrid_coco.hosts.marker import (
    add_agent,
    marker_is_active,
    marker_path,
    project_id_from_path,
    read_marker,
)
from hybrid_coco.hosts.runtime import find_index_root
from hybrid_coco.indexer import index_path


def test_write_project_awareness_copies_packaged_file(tmp_path: Path):
    dst = write_project_awareness(tmp_path)
    assert dst == tmp_path / AWARENESS_REL
    text = dst.read_text(encoding="utf-8")
    assert "hc_file_context" in text
    assert "Decision tree" in text


def test_install_global_claude_preserves_user_content_and_is_idempotent(tmp_path: Path):
    path = tmp_path / ".claude" / "CLAUDE.md"
    path.parent.mkdir()
    path.write_text("# Existing\n\nUser content.\n", encoding="utf-8")
    dest = install_global_instructions(home=tmp_path, host="claude")
    assert dest == path
    first = path.read_text(encoding="utf-8")
    assert "# Existing\n\nUser content.\n" in first
    assert first.count(SECTION_START) == 1
    assert first.count(SECTION_END) == 1
    assert GLOBAL_BODY.strip() in first
    assert "Decision tree" not in first
    install_global_instructions(home=tmp_path, host="claude")
    assert path.read_text(encoding="utf-8") == first


def test_install_global_cursor_overwrites_managed_rule(tmp_path: Path):
    dest = install_global_instructions(home=tmp_path, host="cursor")
    assert dest == tmp_path / ".cursor" / "rules" / "hybrid-coco.mdc"
    text = dest.read_text(encoding="utf-8")
    assert text == CURSOR_GLOBAL_RULE
    assert "alwaysApply: true" in text
    assert "Decision tree" not in text
    dest.write_text("stale\n", encoding="utf-8")
    install_global_instructions(home=tmp_path, host="cursor")
    assert dest.read_text(encoding="utf-8") == CURSOR_GLOBAL_RULE


def test_upsert_rejects_malformed_markers(tmp_path: Path):
    path = tmp_path / "CLAUDE.md"
    path.write_text(SECTION_START + "\norphan\n", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed managed section"):
        upsert_managed_section(
            path=path,
            start=SECTION_START,
            end=SECTION_END,
            content=GLOBAL_BODY,
        )


def test_upsert_rejects_empty_content(tmp_path: Path):
    with pytest.raises(ValueError, match="managed section content is empty"):
        upsert_managed_section(
            path=tmp_path / "CLAUDE.md",
            start=SECTION_START,
            end=SECTION_END,
            content="   \n",
        )


def test_strip_legacy_global_include_preserves_user_text(tmp_path: Path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "hybrid-coco.md").write_text("stale protocol\n", encoding="utf-8")
    (claude_dir / "CLAUDE.md").write_text(
        "# Mine\n\n@hybrid-coco.md\n\nKeep me.\n",
        encoding="utf-8",
    )
    actions = strip_legacy_global_claude_include(tmp_path)
    assert "removed ~/.claude/hybrid-coco.md" in actions
    assert "removed @hybrid-coco.md from ~/.claude/CLAUDE.md" in actions
    assert not (claude_dir / "hybrid-coco.md").exists()
    leftover = (claude_dir / "CLAUDE.md").read_text(encoding="utf-8")
    assert "# Mine" in leftover
    assert "Keep me." in leftover
    assert "@hybrid-coco.md" not in leftover


def test_strip_legacy_deletes_file_that_only_had_the_include(tmp_path: Path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "CLAUDE.md").write_text("@hybrid-coco.md\n", encoding="utf-8")
    strip_legacy_global_claude_include(tmp_path)
    assert not (claude_dir / "CLAUDE.md").exists()


def test_apply_project_instructions_rejects_unknown_host(tmp_path: Path):
    with pytest.raises(ValueError, match="unknown host"):
        apply_project_instructions(root=tmp_path, host="nope", home=tmp_path / "home")


def test_apply_project_instructions_does_not_write_project_instruction_files(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "proj"
    root.mkdir()
    apply_project_instructions(root=root, host="claude", home=home)
    assert not (root / "AGENTS.md").exists()
    assert not (root / "CLAUDE.md").exists()
    global_md = (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert SECTION_START in global_md
    assert GLOBAL_BODY.strip() in global_md
    assert "Decision tree" not in global_md
    marker = read_marker(root)
    assert marker is not None
    assert marker["id"] == project_id_from_path(root.resolve())
    assert marker["agents"] == ["claude"]
    awareness = (root / AWARENESS_REL).read_text(encoding="utf-8")
    assert "Decision tree" in awareness


def test_marker_add_agent_is_idempotent(tmp_path: Path):
    assert add_agent(tmp_path, "claude") is True
    data = json.loads(marker_path(tmp_path).read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["id"] == project_id_from_path(tmp_path.resolve())
    assert data["agents"] == ["claude"]
    assert add_agent(tmp_path, "claude") is False
    assert add_agent(tmp_path, "cursor") is True
    assert read_marker(tmp_path)["agents"] == ["claude", "cursor"]


def test_marker_rejects_unknown_agent(tmp_path: Path):
    with pytest.raises(ValueError, match="unknown host"):
        add_agent(tmp_path, "nope")


def test_marker_rejects_invalid_existing_file(tmp_path: Path):
    path = marker_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text('{"version": 1}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="missing required key: id"):
        read_marker(tmp_path)
    assert marker_is_active(tmp_path) is False


def test_marker_empty_id_is_inactive(tmp_path: Path):
    path = marker_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"version": 1, "id": "", "agents": ["claude"]}) + "\n",
        encoding="utf-8",
    )
    assert marker_is_active(tmp_path) is False


def test_find_index_root_requires_marker_and_index(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "sample.py").write_text("def greet():\n    return 1\n", encoding="utf-8")
    index_path(tmp_path)
    assert find_index_root(tmp_path) is None
    add_agent(tmp_path, "claude")
    assert find_index_root(tmp_path) == tmp_path.resolve()
    assert find_index_root(src) == tmp_path.resolve()


def test_install_instructions_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    runner = CliRunner()
    result = runner.invoke(main, ["install-instructions", "--host", "claude"])
    assert result.exit_code == 0, result.output
    text = (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert SECTION_START in text
    assert "Decision tree" not in text
    result2 = runner.invoke(main, ["install-instructions", "--host", "all"])
    assert result2.exit_code == 0, result2.output
    assert (home / ".cursor" / "rules" / "hybrid-coco.mdc").is_file()
    assert (home / ".codex" / "AGENTS.md").is_file()
    assert (home / ".config" / "opencode" / "AGENTS.md").is_file()
    assert (home / ".config" / "devin" / "AGENTS.md").is_file()
