"""Tests for the unified language registry."""

from __future__ import annotations

from hybrid_coco.languages.registry import (
    EXTENSION_MAP,
    KNOWN_LANGUAGES,
    LANGUAGE_SPECS,
    create_parser,
    detect_language,
    get_language_spec,
    get_structure_query,
    load_tree_sitter,
)
from hybrid_coco.structure import STRUCTURE_KINDS


def test_extension_map_matches_legacy_entries():
    assert detect_language("main.py") == "python"
    assert detect_language("App.tsx") == "tsx"
    assert detect_language("util.hpp") == "cpp"
    assert detect_language("build.kts") == "kotlin"
    assert EXTENSION_MAP[".jsx"] == "javascript"
    assert EXTENSION_MAP[".h"] == "c"


def test_known_languages_complete():
    names = {spec.name for spec in LANGUAGE_SPECS}
    assert names == KNOWN_LANGUAGES
    assert len(names) == 12


def test_each_language_has_parser_and_structure_queries():
    for spec in LANGUAGE_SPECS:
        assert spec.extensions, f"{spec.name} has no extensions"
        for kind in STRUCTURE_KINDS:
            assert get_structure_query(spec.name, kind), f"{spec.name} missing {kind} query"
        parser = create_parser(spec.name)
        assert parser is not None


def test_tree_sitter_loaders_work():
    for spec in LANGUAGE_SPECS:
        lang = load_tree_sitter(spec.name)
        assert lang is not None
        assert get_language_spec(spec.name) is spec


def test_no_duplicate_extensions():
    seen: set[str] = set()
    for spec in LANGUAGE_SPECS:
        for ext in spec.extensions:
            assert ext not in seen, f"duplicate extension {ext}"
            seen.add(ext)
