"""mnemo-style install: global short gate; project init only writes the marker."""

from __future__ import annotations

from pathlib import Path

from .common import ASSETS_DIR
from .marker import add_agent

SECTION_START = "<!-- hybrid-coco:start -->"
SECTION_END = "<!-- hybrid-coco:end -->"
AWARENESS_REL = Path(".hybrid-coco") / "hybrid-coco.md"
LEGACY_GLOBAL_INCLUDE = "@hybrid-coco.md"

# same shape as mnemo templates/rules/global.md — conditional on the marker.
GLOBAL_BODY = (
    "## hybrid-coco\n"
    "\n"
    "In repositories initialized with hybrid-coco (a valid "
    "`.hybrid-coco/project.json` with a non-empty `id` exists at the project "
    "root), prefer `hc_*` MCP tools over native Read/Grep (or the host equivalent).\n"
    "\n"
    "When the marker is valid:\n"
    "- Use `hc_symbol`, `hc_search`, `hc_file_context`, `hc_snippet`, "
    "`hc_structure`, `hc_status`\n"
    "- Load the `hybrid-coco` skill when it is available (`/hc-init`, `/hc-search`)\n"
    "- After a hit, read bodies with `hc_snippet` — not the whole file\n"
    "\n"
    "If the marker is missing, malformed, or has no `id`, skip hybrid-coco "
    "entirely for that project.\n"
)

CURSOR_GLOBAL_RULE = (
    "---\n"
    "description: Prefer hybrid-coco hc_* tools in initialized projects\n"
    "alwaysApply: true\n"
    "---\n\n"
    f"{GLOBAL_BODY}"
)


def write_project_awareness(root: Path) -> Path:
    src = ASSETS_DIR / "hybrid-coco.md"
    if not src.is_file():
        raise FileNotFoundError(f"packaged awareness missing: {src}")
    dst = root / AWARENESS_REL
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def upsert_managed_section(*, path: Path, start: str, end: str, content: str) -> bool:
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
        updated = _append_section(existing, block)

    if updated == existing:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")
    return True


def _append_section(existing: str, addition: str) -> str:
    if existing == "":
        return addition + "\n"
    if existing.endswith("\n\n"):
        return existing + addition + "\n"
    if existing.endswith("\n"):
        return existing + "\n" + addition + "\n"
    return existing + "\n\n" + addition + "\n"


def global_instruction_path(home: Path, host: str) -> Path:
    if host == "claude":
        return home / ".claude" / "CLAUDE.md"
    if host == "cursor":
        return home / ".cursor" / "rules" / "hybrid-coco.mdc"
    if host == "codex":
        return home / ".codex" / "AGENTS.md"
    if host == "opencode":
        return home / ".config" / "opencode" / "AGENTS.md"
    if host == "devin":
        return home / ".config" / "devin" / "AGENTS.md"
    raise ValueError(f"unknown host: {host}")


def install_global_instructions(*, home: Path, host: str) -> Path:
    path = global_instruction_path(home, host)
    if host == "cursor":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(CURSOR_GLOBAL_RULE, encoding="utf-8")
        return path
    upsert_managed_section(
        path=path,
        start=SECTION_START,
        end=SECTION_END,
        content=GLOBAL_BODY,
    )
    return path


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
    dest = install_global_instructions(home=home, host=host)
    lines.append(f"global instructions: {dest}")
    return lines
