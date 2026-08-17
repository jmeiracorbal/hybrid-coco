"""Language registry — extension map, parsers, tree-sitter loaders, structure queries."""

from .registry import (
    EXTENSION_MAP,
    KNOWN_LANGUAGES,
    LANGUAGE_SPECS,
    LanguageSpec,
    create_parser,
    detect_language,
    get_language_spec,
    get_structure_query,
    load_tree_sitter,
)

__all__ = [
    "EXTENSION_MAP",
    "KNOWN_LANGUAGES",
    "LANGUAGE_SPECS",
    "LanguageSpec",
    "create_parser",
    "detect_language",
    "get_language_spec",
    "get_structure_query",
    "load_tree_sitter",
]
