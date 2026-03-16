"""SQLite store: schema creation, file and symbol CRUD."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

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

    def lookup_symbol(self, name: str) -> list[dict]:
        """Exact name lookup (case-insensitive), then prefix fallback."""
        rows = self._conn.execute(
            """SELECT s.*, f.path, f.language FROM symbols s
               JOIN files f ON f.id = s.file_id
               WHERE lower(s.name) = lower(?)
               ORDER BY s.kind, f.path, s.line_start
               LIMIT 20""",
            (name,),
        ).fetchall()
        if not rows:
            # prefix fallback
            rows = self._conn.execute(
                """SELECT s.*, f.path, f.language FROM symbols s
                   JOIN files f ON f.id = s.file_id
                   WHERE lower(s.name) LIKE lower(?) || '%'
                   ORDER BY s.kind, f.path, s.line_start
                   LIMIT 20""",
                (name,),
            ).fetchall()
        return [dict(r) for r in rows]

    def fts_search(self, query: str, limit: int = 20) -> list[dict]:
        """FTS5 trigram search over symbols."""
        try:
            rows = self._conn.execute(
                """SELECT s.*, f.path FROM symbols s
                   JOIN files f ON f.id = s.file_id
                   WHERE s.id IN (
                       SELECT rowid FROM symbols_fts WHERE symbols_fts MATCH ?
                   )
                   ORDER BY f.path, s.line_start
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []

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
