"""Minimal tests for Fase 1: indexer, store, CLI."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from hybrid_coco.cli import main
from hybrid_coco.config import get_index_path
from hybrid_coco.indexer import index_path


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_PYTHON = textwrap.dedent("""\
    class Greeter:
        '''A simple greeter.'''
        def greet(self, name: str) -> str:
            '''Return a greeting string.'''
            return f"Hello, {name}!"

    def standalone(x: int) -> int:
        '''Double the value.'''
        return x * 2
""")


@pytest.fixture()
def fixture_dir(tmp_path: Path) -> Path:
    """Create a minimal fixture directory with one Python file."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "sample.py").write_text(SAMPLE_PYTHON)
    return tmp_path


# ── Test 1: basic indexing ────────────────────────────────────────────────────

def test_index_creates_symbols(fixture_dir: Path):
    result = index_path(fixture_dir)
    assert result.indexed == 1
    assert result.errors == 0

    db = get_index_path(fixture_dir)
    assert db.exists()

    from hybrid_coco.store import Store
    store = Store(db)
    try:
        stats = store.stats()
        assert stats["files"] == 1
        assert stats["symbols"] > 0

        # Should have class Greeter and function standalone
        syms = store.lookup_symbol("Greeter")
        assert syms, "Expected to find 'Greeter' symbol"
        assert syms[0]["kind"] == "class"

        syms2 = store.lookup_symbol("standalone")
        assert syms2, "Expected to find 'standalone' symbol"
        assert syms2[0]["kind"] == "function"
    finally:
        store.close()


# ── Test 2: incremental indexing ──────────────────────────────────────────────

def test_incremental_no_change(fixture_dir: Path):
    # First index
    r1 = index_path(fixture_dir)
    assert r1.indexed == 1

    # Second index — no changes
    r2 = index_path(fixture_dir)
    assert r2.indexed == 0
    assert r2.skipped == 1


def test_incremental_change(fixture_dir: Path):
    # First index
    index_path(fixture_dir)

    # Modify file
    f = fixture_dir / "src" / "sample.py"
    f.write_text(SAMPLE_PYTHON + "\ndef extra(): pass\n")

    # Second index — only one file re-indexed
    r2 = index_path(fixture_dir)
    assert r2.indexed == 1
    assert r2.skipped == 0


# ── Test 3: hc status CLI ─────────────────────────────────────────────────────

def test_cli_status(fixture_dir: Path):
    # Must index first
    index_path(fixture_dir)

    runner = CliRunner()
    result = runner.invoke(main, ["status", str(fixture_dir)])
    assert result.exit_code == 0
    assert "Files:" in result.output
    assert "Symbols:" in result.output
    assert "Updated:" in result.output


# ── Test 4: hc query ──────────────────────────────────────────────────────────

def test_cli_query(fixture_dir: Path, monkeypatch: pytest.MonkeyPatch):
    index_path(fixture_dir)
    monkeypatch.chdir(fixture_dir)

    runner = CliRunner()
    result = runner.invoke(main, ["query", "greeting"])
    assert result.exit_code == 0

    result2 = runner.invoke(main, ["query", "standalone"])
    assert result2.exit_code == 0
    assert "standalone" in result2.output
