"""Snapshot tests for shared query formatters across CLI, MCP, and hooks."""

from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from hybrid_coco.cli import main
from hybrid_coco.config import get_index_path
from hybrid_coco.formatters import OutputStyle, format_file_context, format_search, format_status, format_structure, format_symbol
from hybrid_coco.hosts.runtime import intercept_grep, intercept_read
from hybrid_coco.indexer import index_path
from hybrid_coco.query import file_context, fts_search, lookup_symbol, open_store, project_stats, structure_search
from hybrid_coco.server import build_server

SAMPLE = textwrap.dedent("""\
    import os

    class Widget:
        '''A widget.'''
        def spin(self) -> None:
            '''Spin the widget.'''
            pass

    def helper(x: int) -> int:
        '''Double x.'''
        return x * 2
""")


@pytest.fixture()
def indexed_project(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "widget.py").write_text(SAMPLE)
    index_path(tmp_path)
    return tmp_path


def _mcp_call(server, name: str, arguments: dict) -> str:
    result = asyncio.run(server.call_tool(name, arguments))
    if isinstance(result, tuple):
        content = result[0]
        return content[0].text if content else ""
    if isinstance(result, str):
        return result
    if hasattr(result, "content"):
        return result.content[0].text
    return str(result)


def test_format_search_styles_match_surfaces(indexed_project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(indexed_project)
    store = open_store(indexed_project)
    try:
        rows = fts_search(store, "helper")
    finally:
        store.close()

    cli_out = format_search("helper", rows, style=OutputStyle.CLI)
    mcp_out = format_search("helper", rows, style=OutputStyle.MCP)
    hook_body = format_search("helper", rows, style=OutputStyle.HOOK)

    runner = CliRunner()
    cli_result = runner.invoke(main, ["query", "helper"])
    assert cli_result.exit_code == 0
    assert cli_result.output.strip() == cli_out.strip()

    server, mcp_store = build_server(indexed_project)
    try:
        mcp_text = _mcp_call(server, "hc_search", {"query": "helper"})
    finally:
        mcp_store.close()
    assert mcp_text == mcp_out

    grep_msg = intercept_grep(indexed_project, "helper")
    assert grep_msg is not None
    assert hook_body in grep_msg


def test_format_symbol_cli_matches_mcp(indexed_project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(indexed_project)
    store = open_store(indexed_project)
    try:
        rows = lookup_symbol(store, "Widget")
    finally:
        store.close()

    expected = format_symbol("Widget", rows, style=OutputStyle.MCP)

    runner = CliRunner()
    cli_result = runner.invoke(main, ["symbol", "Widget"])
    assert cli_result.exit_code == 0
    assert cli_result.output.strip() == expected.strip()

    server, mcp_store = build_server(indexed_project)
    try:
        mcp_text = _mcp_call(server, "hc_symbol", {"name": "Widget"})
    finally:
        mcp_store.close()
    assert mcp_text == expected


def test_format_file_context_cli_matches_mcp(indexed_project: Path, monkeypatch: pytest.MonkeyPatch):
    rel = "src/widget.py"
    store = open_store(indexed_project)
    try:
        data = file_context(store, rel)
    finally:
        store.close()
    assert data is not None

    cli_fmt = format_file_context(rel, data, style=OutputStyle.CLI)
    mcp_fmt = format_file_context(rel, data, style=OutputStyle.MCP)
    assert cli_fmt == mcp_fmt

    monkeypatch.chdir(indexed_project)
    runner = CliRunner()
    cli_result = runner.invoke(main, ["file-context", rel])
    assert cli_result.exit_code == 0
    assert cli_result.output.strip() == cli_fmt

    server, mcp_store = build_server(indexed_project)
    try:
        mcp_text = _mcp_call(server, "hc_file_context", {"path": rel})
    finally:
        mcp_store.close()
    assert mcp_text == mcp_fmt


def test_format_file_context_hook_uses_fixed_kind_order(indexed_project: Path):
    rel = "src/widget.py"
    store = open_store(indexed_project)
    try:
        data = file_context(store, rel)
    finally:
        store.close()
    assert data is not None

    hook_fmt = format_file_context(rel, data, style=OutputStyle.HOOK)
    read_msg = intercept_read(indexed_project, rel, None, None)
    assert read_msg is not None
    assert hook_fmt in read_msg
    assert "Classes (1):" in hook_fmt
    assert "Functions (1):" in hook_fmt
    assert "Methods (1):" in hook_fmt
    assert "Imports (1):" in hook_fmt


def test_format_status_cli_matches_mcp(indexed_project: Path):
    db = get_index_path(indexed_project)
    store = open_store(indexed_project)
    try:
        stats = project_stats(store)
    finally:
        store.close()

    expected = format_status(stats, db)

    runner = CliRunner()
    cli_result = runner.invoke(main, ["status", str(indexed_project)])
    assert cli_result.exit_code == 0
    assert cli_result.output.strip() == expected.strip()

    server, mcp_store = build_server(indexed_project)
    try:
        mcp_text = _mcp_call(server, "hc_status", {})
    finally:
        mcp_store.close()
    assert mcp_text == expected


def test_format_structure_cli_matches_mcp(indexed_project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(indexed_project)
    store = open_store(indexed_project)
    try:
        matches = structure_search(indexed_project, store, "function")
    finally:
        store.close()

    cli_fmt = format_structure("function", matches, style=OutputStyle.CLI)
    mcp_fmt = format_structure("function", matches, style=OutputStyle.MCP)

    runner = CliRunner()
    cli_result = runner.invoke(main, ["structure", "function"])
    assert cli_result.exit_code == 0
    if matches:
        assert cli_result.output.strip() == cli_fmt
    else:
        assert cli_result.output.strip() == "No results."

    server, mcp_store = build_server(indexed_project)
    try:
        mcp_text = _mcp_call(server, "hc_structure", {"kind": "function"})
    finally:
        mcp_store.close()
    assert mcp_text == mcp_fmt


def test_mcp_empty_search_message(indexed_project: Path):
    server, store = build_server(indexed_project)
    try:
        text = _mcp_call(server, "hc_search", {"query": "zzzznotfound999"})
    finally:
        store.close()
    assert text == "# hc_search('zzzznotfound999')\nNo results."


def test_mcp_missing_file_context(indexed_project: Path):
    server, store = build_server(indexed_project)
    try:
        text = _mcp_call(server, "hc_file_context", {"path": "missing.py"})
    finally:
        store.close()
    assert text == "File 'missing.py' not found in index."
