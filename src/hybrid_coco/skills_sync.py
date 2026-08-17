"""Keep repo skill mirrors aligned with packaged Claude skills."""

from __future__ import annotations

import shutil
from pathlib import Path

from .hosts.common import ASSETS_DIR, SKILL_NAMES

_SKILLS_SRC = ASSETS_DIR / "skills"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def mirror_targets(root: Path | None = None) -> tuple[Path, Path]:
    base = root if root is not None else repo_root()
    return base / "skills", base / "plugin" / "skills"


def _collect_files(base: Path) -> dict[str, Path]:
    if not base.is_dir():
        raise FileNotFoundError(f"skills tree missing: {base}")
    files: dict[str, Path] = {}
    for path in sorted(base.rglob("*")):
        if path.is_file():
            files[path.relative_to(base).as_posix()] = path
    return files


def diff_trees(src: Path, dst: Path) -> list[str]:
    src_files = _collect_files(src)
    dst_files = _collect_files(dst) if dst.is_dir() else {}

    diffs: list[str] = []
    for rel in sorted(set(src_files) | set(dst_files)):
        src_path = src_files.get(rel)
        dst_path = dst_files.get(rel)
        if src_path is None:
            diffs.append(f"extra: {dst / rel}")
            continue
        if dst_path is None:
            diffs.append(f"missing: {dst / rel}")
            continue
        if src_path.read_bytes() != dst_path.read_bytes():
            diffs.append(f"changed: {dst / rel}")
    return diffs


def verify_mirrors(root: Path | None = None) -> list[str]:
    """Return drift messages; empty list means all mirrors match the source."""
    src = _SKILLS_SRC
    issues: list[str] = []
    for dst in mirror_targets(root):
        for line in diff_trees(src, dst):
            issues.append(f"{line} (expected mirror of {src})")
    return issues


def sync_mirrors(root: Path | None = None) -> list[str]:
    """Replace repo mirrors with a copy of packaged Claude skills."""
    src = _SKILLS_SRC
    if not src.is_dir():
        raise FileNotFoundError(f"packaged skills missing: {src}")

    for name in SKILL_NAMES:
        skill_md = src / name / "SKILL.md"
        if not skill_md.is_file():
            raise FileNotFoundError(f"packaged skill missing: {skill_md}")

    actions: list[str] = []
    for dst in mirror_targets(root):
        if dst.exists():
            shutil.rmtree(dst)
            actions.append(f"removed {dst}")
        shutil.copytree(src, dst)
        actions.append(f"copied {src} → {dst}")
    return actions
