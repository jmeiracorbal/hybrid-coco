"""Language detection and parser registry."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .base import Parser, Symbol

log = logging.getLogger(__name__)

# Extension → language name
_EXT_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
    ".cs": "csharp",
    ".kt": "kotlin",
    ".kts": "kotlin",
}

# Lazy-loaded parser cache
_PARSERS: dict[str, Parser] = {}


def detect_language(path: str | Path) -> Optional[str]:
    """Return language name for a file path, or None if unsupported."""
    suffix = Path(path).suffix.lower()
    return _EXT_MAP.get(suffix)


def get_parser(language: str) -> Optional[Parser]:
    """Return (and cache) a parser instance for the given language."""
    if language in _PARSERS:
        return _PARSERS[language]

    try:
        if language == "python":
            from .python_parser import PythonParser
            parser = PythonParser()
        elif language in ("javascript",):
            from .js_parser import JSParser
            parser = JSParser("javascript")
        elif language == "typescript":
            from .js_parser import JSParser
            parser = JSParser("typescript")
        elif language == "tsx":
            from .js_parser import JSParser
            parser = JSParser("tsx")
        elif language == "rust":
            from .rust_parser import RustParser
            parser = RustParser()
        elif language == "go":
            from .go_parser import GoParser
            parser = GoParser()
        elif language == "java":
            from .java_parser import JavaParser
            parser = JavaParser()
        elif language == "c":
            from .c_parser import CFamilyParser
            parser = CFamilyParser("c")
        elif language == "cpp":
            from .c_parser import CFamilyParser
            parser = CFamilyParser("cpp")
        elif language == "csharp":
            from .csharp_parser import CSharpParser
            parser = CSharpParser()
        elif language == "kotlin":
            from .kotlin_parser import KotlinParser
            parser = KotlinParser()
        else:
            return None

        _PARSERS[language] = parser
        return parser

    except Exception as exc:
        log.error("Failed to load parser for %s: %s", language, exc)
        return None


def parse_file(path: Path, source: bytes) -> list[Symbol]:
    """Parse a file and return its symbols, or [] on error/unsupported."""
    lang = detect_language(path)
    if lang is None:
        return []
    parser = get_parser(lang)
    if parser is None:
        return []
    return parser.parse(source, str(path))
