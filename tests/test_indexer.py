"""Minimal tests for Fase 1: indexer, store, CLI."""

from __future__ import annotations

import json
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


def test_cli_query(fixture_dir: Path, monkeypatch: pytest.MonkeyPatch):
    index_path(fixture_dir)
    monkeypatch.chdir(fixture_dir)

    runner = CliRunner()
    result = runner.invoke(main, ["query", "greeting"])
    assert result.exit_code == 0

    result2 = runner.invoke(main, ["query", "standalone"])
    assert result2.exit_code == 0
    assert "standalone" in result2.output


# ── Test 5: --exclude ─────────────────────────────────────────────────────────

def test_exclude_skips_matching_files(fixture_dir: Path):
    vendor = fixture_dir / "vendor"
    vendor.mkdir()
    (vendor / "lib.py").write_text("def vendored():\n    return 1\n")

    result = index_path(fixture_dir, exclude=("vendor/**",))
    assert result.indexed == 1
    assert result.errors == 0

    from hybrid_coco.store import Store
    store = Store(get_index_path(fixture_dir))
    try:
        assert store.lookup_symbol("Greeter")
        assert not store.lookup_symbol("vendored")
        assert store.stats()["files"] == 1
    finally:
        store.close()


def test_exclude_removes_previously_indexed(fixture_dir: Path):
    vendor = fixture_dir / "vendor"
    vendor.mkdir()
    (vendor / "lib.py").write_text("def vendored():\n    return 1\n")

    index_path(fixture_dir)
    from hybrid_coco.store import Store
    store = Store(get_index_path(fixture_dir))
    try:
        assert store.lookup_symbol("vendored")
    finally:
        store.close()

    result = index_path(fixture_dir, exclude=("vendor/**",))
    assert result.removed == 1

    store = Store(get_index_path(fixture_dir))
    try:
        assert not store.lookup_symbol("vendored")
        assert store.stats()["files"] == 1
    finally:
        store.close()


def test_exclude_empty_pattern_fails(fixture_dir: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["index", str(fixture_dir), "--exclude", ""])
    assert result.exit_code == 1
    assert "non-empty" in result.output


# ── Test 6: hc init writes .gitignore ─────────────────────────────────────────

def test_init_adds_hybrid_coco_gitignore(fixture_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(fixture_dir)])
    assert result.exit_code == 0, result.output

    gi = (fixture_dir / ".gitignore").read_text(encoding="utf-8")
    assert ".hybrid-coco/" in gi
    assert (fixture_dir / ".hybrid-coco" / "config.toml").is_file()

    # idempotent
    result2 = runner.invoke(main, ["init", str(fixture_dir)])
    assert result2.exit_code == 0
    assert (fixture_dir / ".gitignore").read_text(encoding="utf-8").count(".hybrid-coco/") == 1


def test_ensure_hc_gitignore_respects_existing_entry(tmp_path: Path):
    from hybrid_coco.indexer import ensure_hc_gitignore

    gi = tmp_path / ".gitignore"
    gi.write_text("node_modules/\n.hybrid-coco/\n")
    assert ensure_hc_gitignore(tmp_path) is False


def test_install_global_writes_skills(tmp_path: Path):
    from hybrid_coco.hosts.claude import ClaudeHost

    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "proj"
    root.mkdir()
    result = ClaudeHost().install(root, global_config=False, home=home)

    assert set(result.skills) == {"hybrid-coco", "hc-init", "hc-search"}
    for name in ("hybrid-coco", "hc-init", "hc-search"):
        skill_md = home / ".claude" / "skills" / name / "SKILL.md"
        assert skill_md.is_file()
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---")
        assert f"name: {name}" in text
    assert (home / ".claude" / "skills" / "hybrid-coco" / "references" / "mcp-tools.md").is_file()

    result2 = ClaudeHost().install(root, global_config=False, home=home)
    assert set(result2.skills) == {"hybrid-coco", "hc-init", "hc-search"}


# ── Test 8: doctor + reset ────────────────────────────────────────────────────

def test_doctor_fails_without_index(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", str(tmp_path)])
    assert result.exit_code == 1
    assert "[fail] index:" in result.output
    assert "FAILED" in result.output


def test_doctor_ok_with_index(fixture_dir: Path):
    index_path(fixture_dir)
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", str(fixture_dir)])
    assert result.exit_code == 0
    assert "[ok] index:" in result.output
    assert "[ok] schema:" in result.output
    assert "[ok] languages:" in result.output
    assert "python" in result.output
    assert "[ok] version:" in result.output
    assert "[ok] settings:" in result.output
    assert "[hint] tool names:" in result.output
    assert "OK" in result.output


def test_reset_removes_index(fixture_dir: Path):
    index_path(fixture_dir)
    db = get_index_path(fixture_dir)
    assert db.exists()

    runner = CliRunner()
    result = runner.invoke(main, ["reset", str(fixture_dir), "-f"])
    assert result.exit_code == 0
    assert not db.exists()
    assert (fixture_dir / ".hybrid-coco" / "config.toml").is_file()

    # re-index works after reset
    r2 = index_path(fixture_dir)
    assert r2.indexed == 1
    assert get_index_path(fixture_dir).exists()


def test_reset_all_removes_mcp_entry(fixture_dir: Path):
    index_path(fixture_dir)
    settings = fixture_dir / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        '{"mcpServers": {"hybrid-coco": {"command": "hc"}, "other": {"command": "x"}}}\n',
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["reset", str(fixture_dir), "-f", "--all"])
    assert result.exit_code == 0
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert "hybrid-coco" not in data["mcpServers"]
    assert "other" in data["mcpServers"]


def test_reset_requires_confirmation_without_force(fixture_dir: Path):
    index_path(fixture_dir)
    runner = CliRunner()
    result = runner.invoke(main, ["reset", str(fixture_dir)], input="n\n")
    assert result.exit_code != 0
    assert get_index_path(fixture_dir).exists()


# ── Test 7: query filters ─────────────────────────────────────────────────────

def test_query_filters_path_lang_pagination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    src = tmp_path / "src"
    other = tmp_path / "other"
    src.mkdir()
    other.mkdir()
    (src / "a.py").write_text("def alpha():\n    '''src alpha'''\n    return 1\n")
    (src / "b.py").write_text("def beta():\n    '''src beta'''\n    return 2\n")
    (other / "c.py").write_text("def alpha():\n    '''other alpha'''\n    return 3\n")

    index_path(tmp_path)
    from hybrid_coco.store import Store

    store = Store(get_index_path(tmp_path))
    try:
        by_path = store.fts_search("alpha", path="src/")
        assert len(by_path) == 1
        assert by_path[0]["path"] == "src/a.py"

        by_lang = store.lookup_symbol("alpha", languages=("python",))
        assert len(by_lang) == 2

        page0 = store.fts_search("src", path="src/", offset=0, limit=1)
        page1 = store.fts_search("src", path="src/", offset=1, limit=1)
        assert len(page0) == 1
        assert len(page1) == 1
        assert page0[0]["path"] != page1[0]["path"]
    finally:
        store.close()

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    r = runner.invoke(main, ["query", "alpha", "--path", "src/"])
    assert r.exit_code == 0
    assert "src/a.py" in r.output
    assert "other/c.py" not in r.output

    r2 = runner.invoke(main, ["symbol", "alpha", "--lang", "python", "--limit", "1"])
    assert r2.exit_code == 0
    assert "alpha" in r2.output

    bad = runner.invoke(main, ["query", "alpha", "--offset", "-1"])
    assert bad.exit_code == 1
    assert "offset" in bad.output


def test_mcp_tool_filters_and_schema(tmp_path: Path):
    import asyncio
    from hybrid_coco.query import parse_query_filters
    from hybrid_coco.server import build_server

    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("def alpha():\n    return 1\n")
    (tmp_path / "b.py").write_text("def alpha():\n    return 2\n")
    index_path(tmp_path)

    path_f, langs, offset, limit = parse_query_filters(
        path="src/", lang=["python"], offset=0, limit=5
    )
    assert path_f == "src/"
    assert langs == ("python",)
    assert offset == 0
    assert limit == 5

    with pytest.raises(ValueError, match="non-empty"):
        parse_query_filters(path="", lang=None, offset=0, limit=5)

    server, store = build_server(tmp_path)
    try:
        tools = asyncio.run(server.list_tools())
        by_name = {t.name: t for t in tools}
        assert "hc_search" in by_name
        assert "hc_symbol" in by_name
        search_schema = by_name["hc_search"].input_schema
        assert "path" in search_schema["properties"]
        assert "lang" in search_schema["properties"]
        assert "offset" in search_schema["properties"]
        assert "limit" in search_schema["properties"]
        assert "path" in by_name["hc_symbol"].input_schema["properties"]

        result = asyncio.run(
            server.call_tool(
                "hc_search",
                {"query": "alpha", "path": "src/", "limit": 10},
            )
        )
        if isinstance(result, tuple):
            content = result[0]
            text = content[0].text if content else ""
        elif isinstance(result, str):
            text = result
        elif hasattr(result, "content"):
            text = result.content[0].text
        else:
            text = str(result)
        assert "src/a.py" in text
        assert "b.py" not in text
    finally:
        store.close()
