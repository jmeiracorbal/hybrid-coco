"""Tests for structural search (phase 07)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from hybrid_coco.cli import main
from hybrid_coco.config import get_index_path
from hybrid_coco.indexer import index_path
from hybrid_coco.store import Store
from hybrid_coco.structure import StructureError, search_structure, validate_structure_kind


@pytest.fixture
def indexed_py_project(tmp_path: Path) -> Path:
    src = tmp_path / "pkg" / "app.py"
    src.parent.mkdir(parents=True)
    src.write_text(
        "import os\n\n"
        "class Greeter:\n"
        "    def greet(self):\n"
        "        return 'hi'\n\n"
        "def top_level():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    index_path(tmp_path)
    return tmp_path


def test_validate_structure_kind_rejects_unknown():
    with pytest.raises(StructureError, match="unknown kind"):
        validate_structure_kind("async")


def test_structure_finds_python_shapes(indexed_py_project: Path):
    store = Store(get_index_path(indexed_py_project))
    try:
        functions = search_structure(indexed_py_project, store, "function")
        methods = search_structure(indexed_py_project, store, "method")
        classes = search_structure(indexed_py_project, store, "class")
        imports = search_structure(indexed_py_project, store, "import")
    finally:
        store.close()

    fn_names = {m.name for m in functions}
    assert "top_level" in fn_names
    assert "greet" not in fn_names

    method_names = {m.name for m in methods}
    assert "greet" in method_names

    class_names = {m.name for m in classes}
    assert "Greeter" in class_names

    assert len(imports) == 1
    assert imports[0].preview.startswith("import os")


def test_structure_path_filter(indexed_py_project: Path):
    store = Store(get_index_path(indexed_py_project))
    try:
        scoped = search_structure(
            indexed_py_project,
            store,
            "function",
            path="pkg/*",
        )
        missing = search_structure(
            indexed_py_project,
            store,
            "function",
            path="other/*",
        )
    finally:
        store.close()

    assert scoped
    assert all(m.path.startswith("pkg/") for m in scoped)
    assert missing == []


def test_cli_structure_ok(indexed_py_project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(indexed_py_project)
    runner = CliRunner()
    result = runner.invoke(main, ["structure", "class"])
    assert result.exit_code == 0
    assert "Greeter" in result.output


def test_cli_structure_unknown_kind_fails(indexed_py_project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(indexed_py_project)
    runner = CliRunner()
    result = runner.invoke(main, ["structure", "async"])
    assert result.exit_code == 1
    assert "unknown kind" in result.output
