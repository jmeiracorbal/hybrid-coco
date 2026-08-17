"""mnemo-style project instruction install: shared AGENTS.md + Claude @AGENTS.md."""

from __future__ import annotations

from pathlib import Path

from .common import ASSETS_DIR
from .marker import add_agent

SECTION_START = "<!-- hybrid-coco:start -->"
SECTION_END = "<!-- hybrid-coco:end -->"
CLAUDE_SECTION_START = "<!-- hybrid-coco:claude-start -->"
CLAUDE_SECTION_END = "<!-- hybrid-coco:claude-end -->"
AGENTS_PRELUDE = "@AGENTS.md"
AWARENESS_REL = Path(".hybrid-coco") / "hybrid-coco.md"
LEGACY_GLOBAL_INCLUDE = "@hybrid-coco.md"

# shared gate for AGENTS.md — short, not the decision-tree protocol.
AGENTS_BODY = (
    "## hybrid-coco\n"
    "\n"
    "This project is indexed with hybrid-coco when `.hybrid-coco/index.db` exists. "
    "Prefer `hc_*` MCP tools over native Read/Grep (or the host equivalent).\n"
    "\n"
    "When the index exists: `hc_symbol`, `hc_search`, `hc_file_context`, "
    "`hc_snippet`, `hc_structure`, `hc_status`. "
    "Skills: `hybrid-coco`, `/hc-init`, `/hc-search`. "
    f"Full protocol: `{AWARENESS_REL.as_posix()}`.\n"
    "\n"
    "If the index is missing, skip hybrid-coco or run `hc init`.\n"
)

# Claude-only extras. shared rules live in AGENTS.md (mnemo claudecode.md split).
CLAUDE_BODY = (
    "### hybrid-coco\n"
    "\n"
    "Prefer `hc_*` MCP tools over Claude Code `Read`/`Grep` when "
    "`.hybrid-coco/index.db` exists. Shared protocol: `AGENTS.md`. "
    f"Full details: `{AWARENESS_REL.as_posix()}`.\n"
)

CURSOR_RULE = (
    "---\n"
    "description: Prefer hybrid-coco hc_* tools when this project is indexed\n"
    "alwaysApply: true\n"
    "---\n\n"
    f"{AGENTS_BODY}"
)


def write_project_awareness(root: Path) -> Path:
    src = ASSETS_DIR / "hybrid-coco.md"
    if not src.is_file():
        raise FileNotFoundError(f"packaged awareness missing: {src}")
    dst = root / AWARENESS_REL
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def upsert_managed_section(
    *,
    path: Path,
    start: str,
    end: str,
    content: str,
    prelude: str,
) -> bool:
    if not start:
        raise ValueError("start marker is empty")
    if not end:
        raise ValueError("end marker is empty")
    if start == end:
        raise ValueError("start and end markers must differ")
    if not content.strip():
        raise ValueError("managed section content is empty")
    if path.exists() and not path.is_file():
        raise ValueError(f"{path} exists and is not a file")

    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    start_count = existing.count(start)
    end_count = existing.count(end)
    if start_count != end_count or start_count > 1:
        raise ValueError(
            f"malformed managed section in {path}: "
            f"found {start_count} {start!r} marker(s) and {end_count} {end!r} marker(s)"
        )

    block = start + "\n" + content.rstrip("\n") + "\n" + end
    if start_count == 1:
        begin = existing.index(start)
        finish = existing.index(end)
        if finish < begin:
            raise ValueError(
                f"malformed managed section in {path}: {end!r} appears before {start!r}"
            )
        finish += len(end)
        updated = existing[:begin] + block + existing[finish:]
    else:
        addition = block
        if prelude != "" and not _contains_line(existing, prelude):
            addition = prelude + "\n\n" + addition
        updated = _append_section(existing, addition)

    if updated == existing:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")
    return True


def _contains_line(content: str, target: str) -> bool:
    for line in content.split("\n"):
        if line.strip() == target:
            return True
    return False


def _append_section(existing: str, addition: str) -> str:
    if existing == "":
        return addition + "\n"
    if existing.endswith("\n\n"):
        return existing + addition + "\n"
    if existing.endswith("\n"):
        return existing + "\n" + addition + "\n"
    return existing + "\n\n" + addition + "\n"


def install_agents_pointer(root: Path) -> bool:
    return upsert_managed_section(
        path=root / "AGENTS.md",
        start=SECTION_START,
        end=SECTION_END,
        content=AGENTS_BODY,
        prelude="",
    )


def install_claude_pointer(root: Path) -> bool:
    install_agents_pointer(root)
    return upsert_managed_section(
        path=root / "CLAUDE.md",
        start=CLAUDE_SECTION_START,
        end=CLAUDE_SECTION_END,
        content=CLAUDE_BODY,
        prelude=AGENTS_PRELUDE,
    )


def install_cursor_rule(root: Path) -> None:
    path = root / ".cursor" / "rules" / "hybrid-coco.mdc"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(CURSOR_RULE, encoding="utf-8")


def strip_legacy_global_claude_include(home: Path) -> list[str]:
    """remove the old unmanaged @hybrid-coco.md line from ~/.claude/CLAUDE.md."""
    actions: list[str] = []
    awareness = home / ".claude" / "hybrid-coco.md"
    if awareness.is_file():
        awareness.unlink()
        actions.append("removed ~/.claude/hybrid-coco.md")

    claude_md = home / ".claude" / "CLAUDE.md"
    if not claude_md.is_file():
        return actions

    text = claude_md.read_text(encoding="utf-8")
    kept = [line for line in text.splitlines(keepends=True) if line.strip() != LEGACY_GLOBAL_INCLUDE]
    updated = "".join(kept)
    if updated == text:
        return actions
    if not updated.strip():
        claude_md.unlink()
        actions.append("removed @hybrid-coco.md from ~/.claude/CLAUDE.md")
        return actions
    claude_md.write_text(updated, encoding="utf-8")
    actions.append("removed @hybrid-coco.md from ~/.claude/CLAUDE.md")
    return actions


def apply_project_instructions(*, root: Path, host: str, home: Path) -> list[str]:
    if host not in {"claude", "cursor", "codex", "opencode", "devin"}:
        raise ValueError(f"unknown host: {host}")

    lines: list[str] = []
    write_project_awareness(root)
    lines.append(f"awareness written to {AWARENESS_REL.as_posix()}")
    add_agent(root, host)
    lines.append(f"project marker: agent {host}")
    lines.extend(strip_legacy_global_claude_include(home))

    if host == "claude":
        install_claude_pointer(root)
        lines.append("project AGENTS.md + CLAUDE.md: hybrid-coco managed sections")
        return lines
    if host == "cursor":
        install_cursor_rule(root)
        lines.append("project .cursor/rules/hybrid-coco.mdc written")
        return lines
    if host in {"codex", "opencode", "devin"}:
        install_agents_pointer(root)
        lines.append("project AGENTS.md: hybrid-coco pointer (managed section)")
        return lines
    raise ValueError(f"unknown host: {host}")
