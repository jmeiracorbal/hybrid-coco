"""tests for project-local instruction pointers."""

from __future__ import annotations

from pathlib import Path

import pytest

from hybrid_coco.hosts.instructions import (
    AWARENESS_REL,
    CLAUDE_POINTER,
    POINTER_BODY,
    SECTION_END,
    SECTION_START,
    apply_project_instructions,
    install_agents_pointer,
    install_claude_pointer,
    strip_legacy_global_claude_include,
    upsert_managed_section,
    write_project_awareness,
)


def test_write_project_awareness_copies_packaged_file(tmp_path: Path):
    dst = write_project_awareness(tmp_path)
    assert dst == tmp_path / AWARENESS_REL
    text = dst.read_text(encoding="utf-8")
    assert "hc_file_context" in text
    assert "Decision tree" in text


def test_upsert_preserves_user_content_and_is_idempotent(tmp_path: Path):
    path = tmp_path / "AGENTS.md"
    path.write_text("# Existing\n\nUser content.\n", encoding="utf-8")
    assert install_agents_pointer(tmp_path) is True
    first = path.read_text(encoding="utf-8")
    assert "# Existing\n\nUser content.\n" in first
    assert first.count(SECTION_START) == 1
    assert first.count(SECTION_END) == 1
    assert POINTER_BODY in first
    assert "Decision tree" not in first
    assert install_agents_pointer(tmp_path) is False
    assert path.read_text(encoding="utf-8") == first


def test_claude_pointer_includes_project_awareness_not_home(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("# Project rules\n", encoding="utf-8")
    assert install_claude_pointer(tmp_path) is True
    text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "# Project rules\n" in text
    assert CLAUDE_POINTER in text
    assert "@.hybrid-coco/hybrid-coco.md" in text
    assert "@hybrid-coco.md\n" not in text.replace("@.hybrid-coco/hybrid-coco.md", "")


def test_upsert_rejects_malformed_markers(tmp_path: Path):
    path = tmp_path / "CLAUDE.md"
    path.write_text(SECTION_START + "\norphan\n", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed managed section"):
        upsert_managed_section(
            path=path,
            start=SECTION_START,
            end=SECTION_END,
            content=POINTER_BODY,
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
