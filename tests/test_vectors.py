"""Tests for optional sqlite-vec embeddings (phase 09)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from click.testing import CliRunner

pytest.importorskip("sqlite_vec")

from hybrid_coco.cli import main
from hybrid_coco.config import get_index_path
from hybrid_coco.indexer import index_path
from hybrid_coco.store import Store
from hybrid_coco.vectors import (
    VectorError,
    VectorExtraMissingError,
    VectorNotReadyError,
    embed_index,
    embedding_status,
    extra_installed,
    semantic_search,
)


def _stub_embed(*, model: str, texts: list[str]) -> list[list[float]]:
    if not model:
        raise VectorError("model must be non-empty")
    vectors: list[list[float]] = []
    for text in texts:
        lowered = text.lower()
        if "alpha" in lowered:
            vectors.append([1.0, 0.0, 0.0])
        elif "beta" in lowered:
            vectors.append([0.0, 1.0, 0.0])
        else:
            vectors.append([0.0, 0.0, 1.0])
    return vectors


def _index_two_functions(root: Path) -> None:
    src = root / "src"
    src.mkdir()
    (src / "a.py").write_text(
        "def alpha():\n    '''alpha helper'''\n    return 1\n",
        encoding="utf-8",
    )
    (root / "b.py").write_text(
        "def beta():\n    '''beta helper'''\n    return 2\n",
        encoding="utf-8",
    )
    index_path(root)


def test_extra_installed():
    assert extra_installed() is True


def test_embed_and_semantic_order(tmp_path: Path):
    _index_two_functions(tmp_path)
    store = Store(get_index_path(tmp_path))
    try:
        with pytest.raises(VectorNotReadyError, match="hc embed --model"):
            semantic_search(
                store=store,
                query="alpha",
                embed_texts=_stub_embed,
            )

        result = embed_index(store=store, model="test-model", embed_texts=_stub_embed)
        assert result.model == "test-model"
        assert result.dimensions == 3
        assert result.vectors == store.stats()["symbols"]

        hits = semantic_search(
            store=store,
            query="looking for alpha",
            embed_texts=_stub_embed,
            limit=1,
        )
        assert len(hits) == 1
        assert hits[0]["name"] == "alpha"
        assert "distance" in hits[0]

        status = embedding_status(store)
        assert status is not None
        assert status.model == "test-model"
        assert status.vectors == result.vectors
    finally:
        store.close()


def test_semantic_path_filter(tmp_path: Path):
    _index_two_functions(tmp_path)
    store = Store(get_index_path(tmp_path))
    try:
        embed_index(store=store, model="test-model", embed_texts=_stub_embed)
        hits = semantic_search(
            store=store,
            query="alpha",
            embed_texts=_stub_embed,
            path="src/",
        )
        assert hits
        assert all(h["path"].startswith("src/") for h in hits)
        empty = semantic_search(
            store=store,
            query="alpha",
            embed_texts=_stub_embed,
            path="missing/",
        )
        assert empty == []
    finally:
        store.close()


def test_embed_rejects_empty_model(tmp_path: Path):
    _index_two_functions(tmp_path)
    store = Store(get_index_path(tmp_path))
    try:
        with pytest.raises(VectorError, match="model must be non-empty"):
            embed_index(store=store, model="  ", embed_texts=_stub_embed)
    finally:
        store.close()


def test_cli_embed_requires_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["embed"])
    assert result.exit_code != 0
    assert "--model" in result.output or "Missing option" in result.output


def test_cli_embed_and_semantic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _index_two_functions(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("hybrid_coco.cli.embed_texts", _stub_embed)

    runner = CliRunner()
    embedded = runner.invoke(main, ["embed", "--model", "test-model"])
    assert embedded.exit_code == 0, embedded.output
    assert "test-model" in embedded.output
    assert "dim=3" in embedded.output

    missing = runner.invoke(main, ["semantic", "alpha", "--path", ""])
    assert missing.exit_code == 1

    searched = runner.invoke(main, ["semantic", "looking for alpha", "--limit", "1"])
    assert searched.exit_code == 0, searched.output
    assert "alpha" in searched.output
    assert "dist=" in searched.output

    doctor = runner.invoke(main, ["doctor", str(tmp_path)])
    assert doctor.exit_code == 0, doctor.output
    assert "[ok] embeddings:" in doctor.output
    assert "test-model" in doctor.output


def test_cli_semantic_without_embed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _index_two_functions(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("hybrid_coco.cli.embed_texts", _stub_embed)
    runner = CliRunner()
    result = runner.invoke(main, ["semantic", "alpha"])
    assert result.exit_code == 1
    assert "hc embed --model" in result.output


def test_doctor_hint_without_vectors(tmp_path: Path):
    _index_two_functions(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", str(tmp_path)])
    assert result.exit_code == 0
    assert "[hint] embeddings:" in result.output
    assert "hc embed --model" in result.output


def test_load_extension_missing_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _index_two_functions(tmp_path)
    store = Store(get_index_path(tmp_path))

    def _raise(_conn):
        raise VectorExtraMissingError()

    monkeypatch.setattr("hybrid_coco.vectors.load_sqlite_vec", _raise)
    try:
        with pytest.raises(VectorExtraMissingError, match="hybrid-coco\\[vec\\]"):
            embed_index(store=store, model="test-model", embed_texts=_stub_embed)
    finally:
        store.close()


def test_mcp_semantic_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from hybrid_coco.server import build_server

    _index_two_functions(tmp_path)
    store = Store(get_index_path(tmp_path))
    try:
        embed_index(store=store, model="test-model", embed_texts=_stub_embed)
    finally:
        store.close()

    monkeypatch.setattr("hybrid_coco.server.embed_texts", _stub_embed)
    server, mcp_store = build_server(tmp_path)
    try:
        tools = asyncio.run(server.list_tools())
        by_name = {t.name: t for t in tools}
        assert "hc_semantic" in by_name
        schema = by_name["hc_semantic"].input_schema
        assert "query" in schema["properties"]
        assert "path" in schema["properties"]
        assert "lang" in schema["properties"]

        result = asyncio.run(
            server.call_tool("hc_semantic", {"query": "looking for alpha", "limit": 1})
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
        assert "alpha" in text
        assert "dist=" in text
    finally:
        mcp_store.close()
