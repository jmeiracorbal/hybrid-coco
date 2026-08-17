"""Health checks for `hc doctor`."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import __version__
from .config import HC_DIR, INDEX_FILE, get_index_path
from .store import Store

_HOOK_NAMES = ("hc-pre-tool-use.sh", "hc-post-tool-use.sh")


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str
    level: str  # "error" | "warn" | "ok" | "info"


@dataclass
class DoctorReport:
    checks: list[DoctorCheck]

    @property
    def ok(self) -> bool:
        return all(c.level != "error" for c in self.checks)


def _check_index_present(root: Path) -> DoctorCheck:
    db = get_index_path(root)
    if not db.is_file():
        return DoctorCheck(
            "index",
            False,
            f"missing at {db} — run: hc index {root}",
            "error",
        )
    return DoctorCheck("index", True, str(db), "ok")


def _check_schema(root: Path) -> DoctorCheck:
    db = get_index_path(root)
    try:
        store = Store(db)
        try:
            stats = store.stats()
            if not store.fts_ready():
                return DoctorCheck("schema", False, "FTS5 table not readable", "error")
        finally:
            store.close()
    except sqlite3.Error as exc:
        return DoctorCheck("schema", False, f"unreadable: {exc}", "error")
    except OSError as exc:
        return DoctorCheck("schema", False, f"unreadable: {exc}", "error")
    return DoctorCheck(
        "schema",
        True,
        f"readable — {stats['files']} files, {stats['symbols']} symbols",
        "ok",
    )


def _check_languages(root: Path) -> DoctorCheck:
    db = get_index_path(root)
    store = Store(db)
    try:
        rows = store.languages()
    finally:
        store.close()
    if not rows:
        return DoctorCheck(
            "languages",
            False,
            "no languages detected (empty or unsupported-only tree)",
            "warn",
        )
    detail = ", ".join(f"{lang}({n})" for lang, n in rows)
    return DoctorCheck("languages", True, detail, "ok")


def _mcp_registered(settings_path: Path) -> bool:
    if not settings_path.is_file():
        return False
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return False
    return "hybrid-coco" in servers


def _check_mcp(root: Path) -> DoctorCheck:
    project = root / ".claude" / "settings.json"
    global_settings = Path.home() / ".claude" / "settings.json"
    project_ok = _mcp_registered(project)
    global_ok = _mcp_registered(global_settings)
    if project_ok or global_ok:
        where = []
        if project_ok:
            where.append(str(project))
        if global_ok:
            where.append(str(global_settings))
        return DoctorCheck("mcp", True, "registered in " + ", ".join(where), "ok")
    return DoctorCheck(
        "mcp",
        False,
        f"hybrid-coco not in {project} or {global_settings} — run: hc init",
        "warn",
    )


def _check_hooks() -> DoctorCheck:
    hooks_dir = Path.home() / ".claude" / "hooks"
    missing = [name for name in _HOOK_NAMES if not (hooks_dir / name).is_file()]
    if missing:
        return DoctorCheck(
            "hooks",
            False,
            f"missing {', '.join(missing)} under {hooks_dir} — run: hc init",
            "warn",
        )
    return DoctorCheck("hooks", True, f"present in {hooks_dir}", "ok")


def _packaging_roots() -> list[Path]:
    """Candidate repo roots that may contain plugin/marketplace version files."""
    pkg = Path(__file__).resolve().parent
    return [
        pkg.parent.parent,  # src/hybrid_coco → repo root
        pkg.parent,         # flat layout
        Path.cwd(),
    ]


def _read_json_version(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if "version" in data and isinstance(data["version"], str):
        return data["version"]
    plugins = data.get("plugins")
    if isinstance(plugins, list) and plugins:
        ver = plugins[0].get("version")
        if isinstance(ver, str):
            return ver
    return None


def _check_versions() -> DoctorCheck:
    package_ver = __version__
    found: list[str] = [f"package={package_ver}"]
    mismatches: list[str] = []

    for root in _packaging_roots():
        market = root / ".claude-plugin" / "marketplace.json"
        plugin = root / "plugin" / ".claude-plugin" / "plugin.json"
        mv = _read_json_version(market)
        pv = _read_json_version(plugin)
        if mv is not None:
            found.append(f"marketplace={mv}")
            if mv != package_ver:
                mismatches.append(f"marketplace.json={mv}")
        if pv is not None:
            found.append(f"plugin={pv}")
            if pv != package_ver:
                mismatches.append(f"plugin.json={pv}")
        if mv is not None or pv is not None:
            break

    if len(found) == 1:
        return DoctorCheck(
            "version",
            True,
            f"{package_ver} (packaging files not present in this install)",
            "ok",
        )
    if mismatches:
        return DoctorCheck(
            "version",
            False,
            f"mismatch — package={package_ver}, " + ", ".join(mismatches),
            "error",
        )
    return DoctorCheck("version", True, ", ".join(found), "ok")


def _check_tool_names_hint() -> DoctorCheck:
    return DoctorCheck(
        "tool names",
        True,
        "hc_* names are part of the public interface; keep them stable and unmodified",
        "info",
    )


def run_doctor(root: Path) -> DoctorReport:
    """Run doctor checks for project root. Index/schema failures are errors."""
    root = root.resolve()
    checks: list[DoctorCheck] = []

    index_check = _check_index_present(root)
    checks.append(index_check)
    if not index_check.ok:
        checks.append(_check_versions())
        checks.append(_check_mcp(root))
        checks.append(_check_hooks())
        checks.append(_check_tool_names_hint())
        return DoctorReport(checks)

    checks.append(_check_schema(root))
    if checks[-1].ok:
        checks.append(_check_languages(root))
    checks.append(_check_versions())
    checks.append(_check_mcp(root))
    checks.append(_check_hooks())
    checks.append(_check_tool_names_hint())
    return DoctorReport(checks)


def format_report(report: DoctorReport) -> str:
    lines = [f"hc doctor (v{__version__})"]
    for c in report.checks:
        tag = {"ok": "ok", "warn": "warn", "error": "fail", "info": "hint"}[c.level]
        lines.append(f"  [{tag}] {c.name}: {c.detail}")
    lines.append("OK" if report.ok else "FAILED")
    return "\n".join(lines)


def reset_index(root: Path, *, wipe_settings: bool) -> list[str]:
    """Remove index (and optionally project MCP entry). Returns action messages."""
    root = root.resolve()
    actions: list[str] = []
    hc_dir = root / HC_DIR
    db = hc_dir / INDEX_FILE

    if db.is_file():
        db.unlink()
        actions.append(f"removed {db}")
    elif hc_dir.is_dir():
        actions.append(f"no index file at {db}")
    else:
        actions.append(f"no index directory at {hc_dir}")

    if hc_dir.is_dir():
        # remove empty dir leftovers (WAL/SHM companions)
        for leftover in hc_dir.iterdir():
            if leftover.is_file():
                leftover.unlink()
                actions.append(f"removed {leftover}")
        try:
            hc_dir.rmdir()
            actions.append(f"removed {hc_dir}")
        except OSError:
            actions.append(f"left {hc_dir} (not empty)")

    if wipe_settings:
        settings_path = root / ".claude" / "settings.json"
        if not settings_path.is_file():
            actions.append(f"no project settings at {settings_path}")
            return actions
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"cannot read {settings_path}: {exc}") from exc
        servers = data.get("mcpServers")
        if isinstance(servers, dict) and "hybrid-coco" in servers:
            del servers["hybrid-coco"]
            settings_path.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
            actions.append(f"removed hybrid-coco MCP entry from {settings_path}")
        else:
            actions.append(f"no hybrid-coco MCP entry in {settings_path}")

    return actions
