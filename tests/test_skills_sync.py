"""Tests for repo skill mirror sync."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from hybrid_coco.cli import main
from hybrid_coco.skills_sync import diff_trees, mirror_targets, sync_mirrors, verify_mirrors


def test_verify_mirrors_in_repo():
    assert verify_mirrors() == []


def test_sync_skills_cli_check_passes():
    runner = CliRunner()
    result = runner.invoke(main, ["sync-skills", "--check"])
    assert result.exit_code == 0
    assert "in sync" in result.output


def test_sync_skills_cli_updates_mirror(tmp_path: Path):
    root = tmp_path / "repo"
    src = root / "src" / "hybrid_coco" / "assets" / "skills"
    src.mkdir(parents=True)
    (src / "hybrid-coco").mkdir()
    (src / "hybrid-coco" / "SKILL.md").write_text("---\nname: hybrid-coco\n---\n", encoding="utf-8")
    (src / "hc-init").mkdir()
    (src / "hc-init" / "SKILL.md").write_text("---\nname: hc-init\n---\n", encoding="utf-8")
    (src / "hc-search").mkdir()
    (src / "hc-search" / "SKILL.md").write_text("---\nname: hc-search\n---\n", encoding="utf-8")

    skills_dst, plugin_dst = mirror_targets(root)
    skills_dst.mkdir(parents=True)
    (skills_dst / "stale.txt").write_text("old\n", encoding="utf-8")

    import hybrid_coco.skills_sync as skills_sync

    original_src = skills_sync._SKILLS_SRC
    skills_sync._SKILLS_SRC = src
    try:
        actions = sync_mirrors(root)
    finally:
        skills_sync._SKILLS_SRC = original_src

    assert any("removed" in line for line in actions)
    assert not (skills_dst / "stale.txt").exists()
    assert (skills_dst / "hybrid-coco" / "SKILL.md").read_text(encoding="utf-8").startswith("---")
    assert (plugin_dst / "hc-search" / "SKILL.md").is_file()


def test_diff_trees_detects_changes(tmp_path: Path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "a.txt").write_text("one\n", encoding="utf-8")
    (dst / "a.txt").write_text("two\n", encoding="utf-8")
    (dst / "extra.txt").write_text("x\n", encoding="utf-8")
    diffs = diff_trees(src, dst)
    assert any("changed:" in line for line in diffs)
    assert any("extra:" in line for line in diffs)
