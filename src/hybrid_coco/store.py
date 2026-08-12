"""SQLite store: schema creation, file and symbol CRUD."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional, Sequence

from .filters import (
    DEFAULT_QUERY_LIMIT,
    matches_path,
    path_filter_spec,
    validate_languages,
    validate_paging,
    validate_path_filter,
)
from .parsers.base import Symbol

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY,
    path        TEXT UNIQUE NOT NULL,
    sha256      TEXT NOT NULL,
    language    TEXT,
    indexed_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS symbols (
    id          INTEGER PRIMARY KEY,
    file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL,
    line_start  INTEGER NOT NULL,
    line_end    INTEGER NOT NULL,
    signature   TEXT,
    docstring   TEXT,
    parent_name TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name, kind, signature, docstring,
    tokenize='trigram'
);
"""


class Store:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._apply_schema()

    def _apply_schema(self):
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self):
        self._conn.close()

    # ── File operations ──────────────────────────────────────────────────────

    def get_file(self, path: str) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM files WHERE path = ?", (path,)
        ).fetchone()

    def upsert_file(self, path: str, sha256: str, language: Optional[str]) -> int:
        """Insert or replace a file record; returns file_id."""
        now = int(time.time())
        cur = self._conn.execute(
            """INSERT INTO files (path, sha256, language, indexed_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(path) DO UPDATE SET
                 sha256=excluded.sha256,
                 language=excluded.language,
                 indexed_at=excluded.indexed_at
               RETURNING id""",
            (path, sha256, language, now),
        )
        row = cur.fetchone()
        self._conn.commit()
        return row[0]

    def delete_file_symbols(self, file_id: int):
        """Delete all symbols (and FTS entries) for a file."""
        # Fetch rowids to delete from FTS
        rows = self._conn.execute(
            "SELECT id FROM symbols WHERE file_id = ?", (file_id,)
        ).fetchall()
        for row in rows:
            self._conn.execute("DELETE FROM symbols_fts WHERE rowid = ?", (row[0],))
        self._conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
        self._conn.commit()

    def delete_file(self, path: str) -> bool:
        """Delete a file row and its symbols. Returns True if a row existed."""
        row = self.get_file(path)
        if row is None:
            return False
        self.delete_file_symbols(row["id"])
        self._conn.execute("DELETE FROM files WHERE id = ?", (row["id"],))
        self._conn.commit()
        return True

    # ── Symbol operations ────────────────────────────────────────────────────

    def insert_symbols(self, file_id: int, symbols: list[Symbol]):
        for sym in symbols:
            cur = self._conn.execute(
                """INSERT INTO symbols
                   (file_id, name, kind, line_start, line_end, signature, docstring, parent_name)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, sym.name, sym.kind, sym.line_start, sym.line_end,
                 sym.signature, sym.docstring, sym.parent_name),
            )
            rowid = cur.lastrowid
            self._conn.execute(
                """INSERT INTO symbols_fts (rowid, name, kind, signature, docstring)
                   VALUES (?, ?, ?, ?, ?)""",
                (rowid, sym.name, sym.kind, sym.signature or "", sym.docstring or ""),
            )
        self._conn.commit()

    # ── Query operations ─────────────────────────────────────────────────────

    def stats(self) -> dict:
        total_files = self._conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        total_symbols = self._conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        by_kind = {}
        for row in self._conn.execute(
            "SELECT kind, COUNT(*) as n FROM symbols GROUP BY kind ORDER BY n DESC"
        ).fetchall():
            by_kind[row["kind"]] = row["n"]
        last_indexed = self._conn.execute(
            "SELECT MAX(indexed_at) FROM files"
        ).fetchone()[0]
        return {
            "files": total_files,
            "symbols": total_symbols,
            "by_kind": by_kind,
            "last_indexed": last_indexed,
        }

    def languages(self) -> list[tuple[str, int]]:
        """Return (language, file_count) pairs ordered by count desc."""
        rows = self._conn.execute(
            """SELECT language, COUNT(*) AS n FROM files
               WHERE language IS NOT NULL
               GROUP BY language ORDER BY n DESC"""
        ).fetchall()
        return [(row["language"], row["n"]) for row in rows]

    def fts_ready(self) -> bool:
        """Return True if the FTS5 table accepts a count query."""
        try:
            self._conn.execute("SELECT count(*) FROM symbols_fts").fetchone()
            return True
        except sqlite3.Error:
            return False

    def _apply_result_filters(
        self,
        rows: list[sqlite3.Row],
        *,
        path: Optional[str],
        languages: Sequence[str],
        offset: int,
        limit: int,
    ) -> list[dict]:
        path_pat = validate_path_filter(path)
        langs = validate_languages(languages)
        validate_paging(offset=offset, limit=limit)

        results = [dict(r) for r in rows]
        if langs:
            lang_set = set(langs)
            results = [
                r for r in results
                if r.get("language") is not None and str(r["language"]).lower() in lang_set
            ]
        if path_pat is not None:
            spec = path_filter_spec(path_pat)
            results = [r for r in results if matches_path(r["path"], spec)]
        return results[offset : offset + limit]

    def lookup_symbol(
        self,
        name: str,
        *,
        path: Optional[str] = None,
        languages: Sequence[str] = (),
        offset: int = 0,
        limit: int = DEFAULT_QUERY_LIMIT,
    ) -> list[dict]:
        """Exact name lookup (case-insensitive), then prefix fallback."""
        rows = self._conn.execute(
            """SELECT s.*, f.path, f.language FROM symbols s
               JOIN files f ON f.id = s.file_id
               WHERE lower(s.name) = lower(?)
               ORDER BY s.kind, f.path, s.line_start""",
            (name,),
        ).fetchall()
        if not rows:
            rows = self._conn.execute(
                """SELECT s.*, f.path, f.language FROM symbols s
                   JOIN files f ON f.id = s.file_id
                   WHERE lower(s.name) LIKE lower(?) || '%'
                   ORDER BY s.kind, f.path, s.line_start""",
                (name,),
            ).fetchall()
        return self._apply_result_filters(
            rows, path=path, languages=languages, offset=offset, limit=limit
        )

    def fts_search(
        self,
        query: str,
        *,
        path: Optional[str] = None,
        languages: Sequence[str] = (),
        offset: int = 0,
        limit: int = DEFAULT_QUERY_LIMIT,
    ) -> list[dict]:
        """FTS5 trigram search over symbols."""
        try:
            rows = self._conn.execute(
                """SELECT s.*, f.path, f.language FROM symbols s
                   JOIN files f ON f.id = s.file_id
                   WHERE s.id IN (
                       SELECT rowid FROM symbols_fts WHERE symbols_fts MATCH ?
                   )
                   ORDER BY f.path, s.line_start""",
                (query,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return self._apply_result_filters(
            rows, path=path, languages=languages, offset=offset, limit=limit
        )

    def file_context(self, path: str) -> dict | None:
        """Return all symbols for a file (relative path). None if file not indexed."""
        row = self._conn.execute(
            "SELECT id, language FROM files WHERE path = ?", (path,)
        ).fetchone()
        if row is None:
            return None
        symbols = self._conn.execute(
            """SELECT name, kind, line_start, line_end, signature, parent_name
               FROM symbols WHERE file_id = ?
               ORDER BY line_start""",
            (row["id"],),
        ).fetchall()
        return {
            "path": path,
            "language": row["language"],
            "symbols": [dict(s) for s in symbols],
        }

    def all_files(self) -> list[sqlite3.Row]:
        return self._conn.execute("SELECT * FROM files ORDER BY path").fetchall()
