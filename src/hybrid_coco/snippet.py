"""Read bounded source slices from disk at query time."""

from __future__ import annotations

from pathlib import Path


class SnippetError(ValueError):
    """Invalid snippet request or missing file."""


def read_snippet(root: Path, path: str, line_start: int, line_end: int) -> str:
    """Return a formatted code slice for path relative to project root."""
    if line_start < 1:
        raise SnippetError("line_start must be >= 1")
    if line_end < line_start:
        raise SnippetError("line_end must be >= line_start")

    rel = path.replace("\\", "/")
    if rel.startswith("/"):
        raise SnippetError(f"invalid path: {path}")

    rel_path = Path(rel)
    if rel_path.is_absolute():
        raise SnippetError(f"invalid path: {path}")
    if ".." in rel_path.parts:
        raise SnippetError(f"path escapes project root: {path}")

    rel = rel_path.as_posix()

    root_resolved = root.resolve()
    file_path = (root_resolved / rel).resolve()
    if not file_path.is_relative_to(root_resolved):
        raise SnippetError(f"path escapes project root: {path}")
    if not file_path.is_file():
        raise SnippetError(f"file not found: {path}")

    text = file_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    total = len(lines)

    if total == 0:
        raise SnippetError(f"file is empty: {path}")
    if line_start > total:
        raise SnippetError(
            f"line_start {line_start} out of range (file has {total} lines)"
        )
    if line_end > total:
        raise SnippetError(
            f"line_end {line_end} out of range (file has {total} lines)"
        )

    selected = lines[line_start - 1 : line_end]
    body = "\n".join(selected)
    header = f"File: {rel}:{line_start}-{line_end} ({len(selected)} lines)\n\n"
    return header + body
