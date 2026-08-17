"""Language detection and parser registry."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Mapping, Optional

from ..languages.registry import KNOWN_LANGUAGES, create_parser, detect_language
from .base import Parser, Symbol

log = logging.getLogger(__name__)

# lazy-loaded parser cache
_PARSERS: dict[str, Parser] = {}


def resolve_language(path: str | Path, language_overrides: Mapping[str, str]) -> Optional[str]:
    """Return language from overrides first, then the built-in extension map."""
    suffix = Path(path).suffix.lower()
    if suffix in language_overrides:
        return language_overrides[suffix]
    return detect_language(path)


def get_parser(language: str) -> Optional[Parser]:
    """Return (and cache) a parser instance for the given language."""
    if language in _PARSERS:
        return _PARSERS[language]

    try:
        parser = create_parser(language)
        if parser is None:
            return None
        _PARSERS[language] = parser
        return parser
    except Exception as exc:
        log.error("Failed to load parser for %s: %s", language, exc)
        return None


def parse_file(path: Path, source: bytes, language_overrides: Mapping[str, str]) -> list[Symbol]:
    """Parse a file and return its symbols, or [] on error/unsupported."""
    lang = resolve_language(path, language_overrides)
    if lang is None:
        return []
    parser = get_parser(lang)
    if parser is None:
        return []
    return parser.parse(source, str(path))
