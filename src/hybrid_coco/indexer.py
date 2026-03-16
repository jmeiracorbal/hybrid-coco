"""Incremental file indexer."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pathspec

from .config import ALWAYS_IGNORE, ensure_index_dir
from .parsers import detect_language, parse_file
from .store import Store

log = logging.getLogger(__name__)

BINARY_CHECK_BYTES = 512


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_binary(data: bytes) -> bool:
    return b"\x00" in data[:BINARY_CHECK_BYTES]


def _load_gitignore(root: Path) -> Optional[pathspec.PathSpec]:
    gi = root / ".gitignore"
    if gi.is_file():
        lines = gi.read_text(encoding="utf-8", errors="replace").splitlines()
        return pathspec.PathSpec.from_lines("gitwildmatch", lines)
    return None


@dataclass
class IndexResult:
    indexed: int = 0
    skipped: int = 0
    errors: int = 0


def _should_skip_dir(name: str) -> bool:
    return name in ALWAYS_IGNORE or name.startswith(".")


def iter_files(root: Path, gitignore: Optional[pathspec.PathSpec]):
    """Walk the tree, yielding Path objects for indexable files."""
    for item in sorted(root.rglob("*")):
        if not item.is_file():
            continue
        # Check if any parent component is in the always-ignore set
        rel = item.relative_to(root)
        parts = rel.parts
        skip = False
        for part in parts[:-1]:  # directories in path
            if part in ALWAYS_IGNORE or (part.startswith(".") and part != "."):
                skip = True
                break
        if skip:
            continue
        # Respect .gitignore
        if gitignore and gitignore.match_file(str(rel)):
            continue
        yield item


def index_path(root: Path, force: bool = False) -> IndexResult:
    """Index all supported files under root (incremental unless force=True)."""
    root = root.resolve()
    db_path = ensure_index_dir(root)
    store = Store(db_path)
    gitignore = _load_gitignore(root)
    result = IndexResult()

    try:
        for filepath in iter_files(root, gitignore):
            rel = str(filepath.relative_to(root))
            try:
                data = filepath.read_bytes()
            except OSError as exc:
                log.warning("Cannot read %s: %s", filepath, exc)
                result.errors += 1
                continue

            if _is_binary(data):
                continue

            lang = detect_language(filepath)
            if lang is None:
                continue  # unsupported extension — skip silently

            sha = _sha256(data)
            existing = store.get_file(rel)

            if not force and existing and existing["sha256"] == sha:
                result.skipped += 1
                continue

            # Re-index: delete old symbols, parse fresh
            file_id = store.upsert_file(rel, sha, lang)
            store.delete_file_symbols(file_id)

            symbols = parse_file(filepath, data)
            store.insert_symbols(file_id, symbols)
            result.indexed += 1
            log.debug("Indexed %s (%d symbols)", rel, len(symbols))

    finally:
        store.close()

    return result
