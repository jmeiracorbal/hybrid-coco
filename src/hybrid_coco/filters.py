"""Query filter validation and path matching."""

from __future__ import annotations

from typing import Optional, Sequence

import pathspec

DEFAULT_QUERY_LIMIT = 20


def validate_paging(*, offset: int, limit: int) -> None:
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if limit < 1:
        raise ValueError("limit must be >= 1")


def validate_languages(languages: Sequence[str]) -> tuple[str, ...]:
    cleaned: list[str] = []
    for lang in languages:
        if not lang or not str(lang).strip():
            raise ValueError("lang must be non-empty")
        cleaned.append(str(lang).strip().lower())
    return tuple(cleaned)


def validate_path_filter(path: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    if not path or not path.strip():
        raise ValueError("path must be non-empty")
    return path.strip()


def path_filter_spec(path: str) -> pathspec.PathSpec:
    return pathspec.PathSpec.from_lines("gitignore", [path])


def matches_path(file_path: str, spec: pathspec.PathSpec) -> bool:
    return spec.match_file(file_path)
