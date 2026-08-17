"""Tests for `.hybrid-coco/config.toml` (phase 08)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from hybrid_coco.cli import main
from hybrid_coco.config import HC_DIR, SETTINGS_FILE, get_index_path
from hybrid_coco.indexer import index_path
from hybrid_coco.settings import SettingsError, load_settings
from hybrid_coco.store import Store


def _write_config(root: Path, body: str) -> None:
    hc = root / HC_DIR
    hc.mkdir(parents=True, exist_ok=True)
    (hc / SETTINGS_FILE).write_text(body, encoding="utf-8")


def test_load_settings_absent_fails(tmp_path: Path):
    with pytest.raises(SettingsError, match="missing"):
        load_settings(tmp_path)


def test_index_writes_default_config(tmp_path: Path):
    (tmp_path / "a.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    index_path(tmp_path)
    cfg = tmp_path / HC_DIR / SETTINGS_FILE
    assert cfg.is_file()
    text = cfg.read_text(encoding="utf-8")
    assert "include = []" in text
    assert "exclude = []" in text
    assert "languages = {}" in text


def test_load_settings_missing_key_fails(tmp_path: Path):
    _write_config(tmp_path, 'exclude = []\nlanguages = {}\n')
    with pytest.raises(SettingsError, match="missing required key 'include'"):
        load_settings(tmp_path)


def test_load_settings_unknown_key_fails(tmp_path: Path):
    _write_config(
        tmp_path,
        'include = []\nexclude = []\nlanguages = {}\nextra = 1\n',
    )
    with pytest.raises(SettingsError, match="unknown keys"):
        load_settings(tmp_path)


def test_load_settings_unknown_language_fails(tmp_path: Path):
    _write_config(
        tmp_path,
        'include = []\nexclude = []\n[languages]\n".py" = "cobol"\n',
    )
    with pytest.raises(SettingsError, match="unknown language"):
        load_settings(tmp_path)


def test_include_limits_indexed_files(tmp_path: Path):
    src = tmp_path / "src"
    other = tmp_path / "other"
    src.mkdir()
    other.mkdir()
    (src / "app.py").write_text("def in_src():\n    return 1\n", encoding="utf-8")
    (other / "lib.py").write_text("def in_other():\n    return 1\n", encoding="utf-8")
    _write_config(
        tmp_path,
        'include = ["src/**"]\nexclude = []\nlanguages = {}\n',
    )

    result = index_path(tmp_path)
    assert result.indexed == 1

    store = Store(get_index_path(tmp_path))
    try:
        assert store.lookup_symbol("in_src")
        assert not store.lookup_symbol("in_other")
    finally:
        store.close()


def test_settings_exclude_and_cli_exclude_combine(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "a.py").write_text("def in_a():\n    return 1\n", encoding="utf-8")
    (b / "b.py").write_text("def in_b():\n    return 1\n", encoding="utf-8")
    (tmp_path / "keep.py").write_text("def keep():\n    return 1\n", encoding="utf-8")
    _write_config(
        tmp_path,
        'include = []\nexclude = ["a/**"]\nlanguages = {}\n',
    )

    result = index_path(tmp_path, exclude=("b/**",))
    assert result.indexed == 1

    store = Store(get_index_path(tmp_path))
    try:
        assert store.lookup_symbol("keep")
        assert not store.lookup_symbol("in_a")
        assert not store.lookup_symbol("in_b")
    finally:
        store.close()


def test_include_removes_previously_indexed(tmp_path: Path):
    src = tmp_path / "src"
    other = tmp_path / "other"
    src.mkdir()
    other.mkdir()
    (src / "app.py").write_text("def in_src():\n    return 1\n", encoding="utf-8")
    (other / "lib.py").write_text("def in_other():\n    return 1\n", encoding="utf-8")

    index_path(tmp_path)
    store = Store(get_index_path(tmp_path))
    try:
        assert store.lookup_symbol("in_other")
    finally:
        store.close()

    _write_config(
        tmp_path,
        'include = ["src/**"]\nexclude = []\nlanguages = {}\n',
    )
    result = index_path(tmp_path)
    assert result.removed == 1

    store = Store(get_index_path(tmp_path))
    try:
        assert store.lookup_symbol("in_src")
        assert not store.lookup_symbol("in_other")
    finally:
        store.close()


def test_language_override_indexes_custom_extension(tmp_path: Path):
    (tmp_path / "mod.pyx").write_text(
        "def cython_fn():\n    return 1\n", encoding="utf-8"
    )
    _write_config(
        tmp_path,
        'include = []\nexclude = []\n[languages]\n".pyx" = "python"\n',
    )

    result = index_path(tmp_path)
    assert result.indexed == 1

    store = Store(get_index_path(tmp_path))
    try:
        langs = dict(store.languages())
        assert langs.get("python") == 1
        assert store.lookup_symbol("cython_fn")
    finally:
        store.close()


def test_cli_index_invalid_settings_fails(tmp_path: Path):
    (tmp_path / "a.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    _write_config(tmp_path, "exclude = []\n")
    runner = CliRunner()
    result = runner.invoke(main, ["index", str(tmp_path)])
    assert result.exit_code == 1
    assert "missing required key" in result.output


def test_reset_keeps_config_toml(tmp_path: Path):
    (tmp_path / "a.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    _write_config(
        tmp_path,
        'include = []\nexclude = []\nlanguages = {}\n',
    )
    index_path(tmp_path)
    cfg = tmp_path / HC_DIR / SETTINGS_FILE
    assert cfg.is_file()

    runner = CliRunner()
    result = runner.invoke(main, ["reset", str(tmp_path), "-f"])
    assert result.exit_code == 0
    assert not get_index_path(tmp_path).exists()
    assert cfg.is_file()
