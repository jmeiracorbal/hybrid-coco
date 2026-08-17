"""Tests for hc snippet (phase 06)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from hybrid_coco.cli import main
from hybrid_coco.snippet import SnippetError, read_snippet


def test_read_snippet_returns_requested_lines(tmp_path: Path):
    src = tmp_path / "src" / "demo.py"
    src.parent.mkdir(parents=True)
    src.write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")

    out = read_snippet(tmp_path, "src/demo.py", 2, 3)
    assert "File: src/demo.py:2-3 (2 lines)" in out
    assert "line2\nline3" in out


def test_read_snippet_rejects_out_of_range(tmp_path: Path):
    src = tmp_path / "a.py"
    src.write_text("only\n", encoding="utf-8")

    with pytest.raises(SnippetError, match="line_end 5 out of range"):
        read_snippet(tmp_path, "a.py", 1, 5)


def test_read_snippet_rejects_missing_file(tmp_path: Path):
    with pytest.raises(SnippetError, match="file not found"):
        read_snippet(tmp_path, "missing.py", 1, 1)


def test_read_snippet_rejects_invalid_range(tmp_path: Path):
    src = tmp_path / "a.py"
    src.write_text("x\n", encoding="utf-8")

    with pytest.raises(SnippetError, match="line_end must be >= line_start"):
        read_snippet(tmp_path, "a.py", 3, 1)


def test_read_snippet_rejects_path_escape(tmp_path: Path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")

    with pytest.raises(SnippetError, match="path escapes project root"):
        read_snippet(tmp_path, "../outside.txt", 1, 1)


def test_cli_snippet_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    src = tmp_path / "mod.py"
    src.write_text("def run():\n    return 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(main, ["snippet", "mod.py", "1", "2"])
    assert result.exit_code == 0
    assert "mod.py:1-2" in result.output
    assert "def run():" in result.output


def test_cli_snippet_missing_file_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["snippet", "nope.py", "1", "1"])
    assert result.exit_code == 1
    assert "file not found" in result.output
