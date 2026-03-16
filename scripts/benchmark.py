#!/usr/bin/env python3
"""
hybrid-coco benchmark: compara tokens de entrada entre grep/read vs hc_* tools.
Uso: python scripts/benchmark.py
"""

import subprocess
import sys
import json
import shutil
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

# ─── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
HC_PROJECT_DIR = SCRIPT_DIR.parent
PROJECT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
INDEX_DB = PROJECT_DIR / ".hybrid-coco" / "index.db"
RESULTS_DIR = SCRIPT_DIR / "benchmark-results"

# Detectar hc: primero en PATH, luego en el venv del proyecto
HC_BIN = shutil.which("hc") or str(HC_PROJECT_DIR / ".venv" / "bin" / "hc")

# ─── Queries ──────────────────────────────────────────────────────────────────

QUERIES = [
    {
        "id": "Q1",
        "description": "Struct que registra el ahorro de tokens",
        "traditional": {"type": "grep", "pattern": "TimedExecution", "path": "src/"},
        "hc": {"type": "hc_symbol", "arg": "TimedExecution"},
    },
    {
        "id": "Q2",
        "description": "Cálculo del porcentaje de ahorro",
        "traditional": {"type": "grep", "pattern": "savings", "path": "src/"},
        "hc": {"type": "hc_search", "arg": "savings"},
    },
    {
        "id": "Q3",
        "description": "Estructura del módulo de tracking",
        "traditional": {"type": "read", "file": "src/tracking.rs"},
        "hc": {"type": "hc_file_context", "arg": "src/tracking.rs"},
    },
    {
        "id": "Q4",
        "description": "Schema de la base de datos SQLite",
        "traditional": {"type": "grep", "pattern": "CREATE TABLE", "path": "src/"},
        "hc": {"type": "hc_search", "arg": "CREATE TABLE"},
    },
    {
        "id": "Q5",
        "description": "Funciones públicas del módulo git",
        "traditional": {"type": "read", "file": "src/git.rs"},
        "hc": {"type": "hc_search", "arg": "git"},
    },
]

MAX_GREP_LINES = 200

# ─── Dataclass ────────────────────────────────────────────────────────────────

@dataclass
class Measurement:
    query_id: str
    description: str
    approach: str           # "traditional" | "hybrid-coco"
    command: str
    output_bytes: int
    output_lines: int
    estimated_tokens: int   # bytes // 4
    truncated: bool


# ─── Prerequisites ────────────────────────────────────────────────────────────

def check_prerequisites():
    errors = []

    if not Path(HC_BIN).exists():
        errors.append(
            f"  hc no encontrado.\n"
            f"  Prueba: cd {HC_PROJECT_DIR} && uv pip install -e . && hc --version"
        )

    if not INDEX_DB.exists():
        errors.append(
            f"  Índice no encontrado: {INDEX_DB}\n"
            f"  Prueba: hc index {PROJECT_DIR}"
        )

    if errors:
        print("ERROR: Prerequisitos faltantes:\n")
        for e in errors:
            print(e)
        sys.exit(1)


# ─── Runners ──────────────────────────────────────────────────────────────────

def run_grep(pattern: str, rel_path: str, cwd: Path) -> tuple[str, str]:
    """Ejecuta grep -rn y devuelve (output, command_str)."""
    cmd = ["grep", "-rn", pattern, rel_path]
    cmd_str = " ".join(cmd)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout + result.stderr, cmd_str


def run_cat(rel_file: str, cwd: Path) -> tuple[str, str]:
    """Ejecuta cat y devuelve (output, command_str)."""
    cmd = ["cat", rel_file]
    cmd_str = " ".join(cmd)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout, cmd_str


def run_hc_query(text: str, cwd: Path) -> tuple[str, str]:
    """Ejecuta hc query y devuelve (output, command_str)."""
    cmd = [HC_BIN, "query", text]
    cmd_str = f"hc query \"{text}\""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout + result.stderr, cmd_str


def run_hc_symbol(name: str, cwd: Path) -> tuple[str, str]:
    """Ejecuta hc symbol y devuelve (output, command_str)."""
    cmd = [HC_BIN, "symbol", name]
    cmd_str = f"hc symbol \"{name}\""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout + result.stderr, cmd_str


def run_hc_file_context(path: str, cwd: Path) -> tuple[str, str]:
    """Ejecuta hc file-context y devuelve (output, command_str)."""
    cmd = [HC_BIN, "file-context", path]
    cmd_str = f"hc file-context \"{path}\""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout + result.stderr, cmd_str


def run_hc_status(cwd: Path) -> dict:
    """Ejecuta hc status y devuelve stats del índice."""
    result = subprocess.run(
        [HC_BIN, "status", "."],
        capture_output=True, text=True, cwd=cwd
    )
    output = result.stdout
    stats = {"files": 0, "symbols": 0, "raw": output.strip()}
    for line in output.splitlines():
        if "Files:" in line:
            try:
                stats["files"] = int(line.split(":")[1].split()[0].strip())
            except (IndexError, ValueError):
                pass
        elif "Symbols:" in line:
            try:
                stats["symbols"] = int(line.split(":")[1].split()[0].strip())
            except (IndexError, ValueError):
                pass
    return stats


# ─── Measurement ──────────────────────────────────────────────────────────────

def measure_traditional(query: dict) -> Measurement:
    trad = query["traditional"]
    kind = trad["type"]

    if kind == "grep":
        raw_output, cmd_str = run_grep(trad["pattern"], trad["path"], PROJECT_DIR)
        lines = raw_output.splitlines()
        truncated = len(lines) > MAX_GREP_LINES
        if truncated:
            output = "\n".join(lines[:MAX_GREP_LINES])
        else:
            output = raw_output

    elif kind == "read":
        output, cmd_str = run_cat(trad["file"], PROJECT_DIR)
        truncated = False

    else:
        raise ValueError(f"Tipo tradicional desconocido: {kind}")

    output_bytes = len(output.encode("utf-8"))
    output_lines = len(output.splitlines())
    return Measurement(
        query_id=query["id"],
        description=query["description"],
        approach="traditional",
        command=cmd_str,
        output_bytes=output_bytes,
        output_lines=output_lines,
        estimated_tokens=output_bytes // 4,
        truncated=truncated,
    )


def measure_hc(query: dict) -> Measurement:
    hc_cfg = query["hc"]
    kind = hc_cfg["type"]

    if kind == "hc_search":
        output, cmd_str = run_hc_query(hc_cfg["arg"], PROJECT_DIR)
    elif kind == "hc_symbol":
        output, cmd_str = run_hc_symbol(hc_cfg["arg"], PROJECT_DIR)
        # Si no hay resultado exacto, intentar con query como fallback
        if "not found" in output.lower() or output.strip() == "":
            output2, cmd_str2 = run_hc_query(hc_cfg["arg"], PROJECT_DIR)
            if output2.strip():
                output = output2
                cmd_str = cmd_str2
    elif kind == "hc_file_context":
        output, cmd_str = run_hc_file_context(hc_cfg["arg"], PROJECT_DIR)
    else:
        raise ValueError(f"Tipo HC desconocido: {kind}")

    output_bytes = len(output.encode("utf-8"))
    output_lines = len(output.splitlines())
    return Measurement(
        query_id=query["id"],
        description=query["description"],
        approach="hybrid-coco",
        command=cmd_str,
        output_bytes=output_bytes,
        output_lines=output_lines,
        estimated_tokens=output_bytes // 4,
        truncated=False,
    )


# ─── Output helpers ───────────────────────────────────────────────────────────

def savings_pct(trad_tokens: int, hc_tokens: int) -> float:
    if trad_tokens == 0:
        return 0.0
    return (trad_tokens - hc_tokens) / trad_tokens * 100


def fmt_num(n: int) -> str:
    return f"{n:,}"


def truncate_desc(s: str, max_len: int = 42) -> str:
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def print_table(pairs: list[tuple[Measurement, Measurement]]):
    col_desc = 42
    col_num = 9

    top    = "┌" + "─"*5 + "┬" + "─"*(col_desc+2) + "┬" + "─"*(col_num+2) + "┬" + "─"*(col_num+2) + "┬" + "─"*9 + "┐"
    head1  = "│ {:<3} │ {:<{w}} │ {:>{n}} │ {:>{n}} │ {:>7} │".format(
        "ID", "Query", "Trad.", "hc", "Savings", w=col_desc, n=col_num)
    head2  = "│ {:<3} │ {:<{w}} │ {:>{n}} │ {:>{n}} │ {:>7} │".format(
        "", "", "tokens", "tokens", "", w=col_desc, n=col_num)
    sep    = "├" + "─"*5 + "┼" + "─"*(col_desc+2) + "┼" + "─"*(col_num+2) + "┼" + "─"*(col_num+2) + "┼" + "─"*9 + "┤"
    bot_sep= "├" + "─"*5 + "┴" + "─"*(col_desc+2) + "┴" + "─"*(col_num+2) + "┴" + "─"*(col_num+2) + "┴" + "─"*9 + "┤"
    bottom = "└" + "─" * (5 + 1 + col_desc+2 + 1 + col_num+2 + 1 + col_num+2 + 1 + 9) + "┘"

    total_trad = sum(t.estimated_tokens for t, _ in pairs)
    total_hc   = sum(h.estimated_tokens for _, h in pairs)
    total_pct  = savings_pct(total_trad, total_hc)

    total_inner_width = 5 + 1 + col_desc+2 + 1 + col_num+2 + 1 + col_num+2 + 1 + 9
    total_label = f" TOTAL"
    total_nums  = f"{fmt_num(total_trad):>{col_num}}  {fmt_num(total_hc):>{col_num}}   {total_pct:>5.1f}%"
    total_line  = f"│ {total_label:<{col_desc + col_num + col_num + 10}} {total_nums} │"

    print(top)
    print(head1)
    print(head2)
    print(sep)

    for trad, hc in pairs:
        pct = savings_pct(trad.estimated_tokens, hc.estimated_tokens)
        trunc_mark = "*" if trad.truncated else ""
        desc = truncate_desc(trad.description)
        line = "│ {:<3} │ {:<{w}} │ {:>{n}} │ {:>{n}} │ {:>6.1f}% │".format(
            trad.query_id,
            desc,
            fmt_num(trad.estimated_tokens) + trunc_mark,
            fmt_num(hc.estimated_tokens),
            pct,
            w=col_desc,
            n=col_num,
        )
        print(line)

    print(bot_sep)
    # Build total line manually for clean alignment
    t_label = "TOTAL"
    t_trad  = fmt_num(total_trad)
    t_hc    = fmt_num(total_hc)
    t_pct   = f"{total_pct:.1f}%"
    inner   = f" {t_label:<{col_desc + 3}} {t_trad:>{col_num}}    {t_hc:>{col_num}}   {t_pct:>6} "
    print(f"│{inner:^{total_inner_width}}│")
    print(bottom)


def print_detail(pairs: list[tuple[Measurement, Measurement]]):
    print("\nDetailed output sizes:")
    for trad, hc in pairs:
        trunc_note = " [TRUNCATED to 200 lines]" if trad.truncated else ""
        print(f"  {trad.query_id} traditional: {trad.command}")
        print(f"       → {trad.output_bytes:,} bytes ({trad.estimated_tokens:,} tokens){trunc_note}")
        print(f"  {hc.query_id} hybrid-coco: {hc.command}")
        print(f"       → {hc.output_bytes:,} bytes ({hc.estimated_tokens:,} tokens)")


# ─── JSON output ──────────────────────────────────────────────────────────────

def save_results(pairs: list[tuple[Measurement, Measurement]], index_stats: dict):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    fname = now.strftime("%Y-%m-%d_%H-%M") + ".json"
    fpath = RESULTS_DIR / fname

    total_trad = sum(t.estimated_tokens for t, _ in pairs)
    total_hc   = sum(h.estimated_tokens for _, h in pairs)
    total_pct  = savings_pct(total_trad, total_hc)

    data = {
        "date": now.isoformat(timespec="seconds"),
        "project": str(PROJECT_DIR),
        "index_stats": {
            "files": index_stats["files"],
            "symbols": index_stats["symbols"],
        },
        "queries": [
            {
                "id": t.query_id,
                "description": t.description,
                "traditional": asdict(t),
                "hybrid_coco": asdict(h),
                "savings_pct": round(savings_pct(t.estimated_tokens, h.estimated_tokens), 1),
            }
            for t, h in pairs
        ],
        "summary": {
            "total_traditional_tokens": total_trad,
            "total_hc_tokens": total_hc,
            "total_savings_pct": round(total_pct, 1),
        },
    }

    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return fpath


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    check_prerequisites()

    index_stats = run_hc_status(PROJECT_DIR)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    print()
    print("hybrid-coco Benchmark")
    print("━" * 66)
    print(f"Project: {PROJECT_DIR} ({index_stats['files']} files, {index_stats['symbols']} symbols)")
    print(f"Date: {now_str}")
    print(f"HC binary: {HC_BIN}")
    print()

    pairs: list[tuple[Measurement, Measurement]] = []
    trad_cmds = set()
    hc_cmds   = set()

    for q in QUERIES:
        print(f"  Running {q['id']}: {q['description']} ...", end=" ", flush=True)
        trad = measure_traditional(q)
        hc   = measure_hc(q)
        pairs.append((trad, hc))
        trad_cmds.add(trad.command.split()[0] + (" -rn" if trad.command.startswith("grep") else ""))
        hc_cmds.add(" ".join(hc.command.split()[:2]))
        pct = savings_pct(trad.estimated_tokens, hc.estimated_tokens)
        print(f"done ({pct:.0f}% savings)")

    print()
    print_table(pairs)
    print()
    total_trad = sum(t.estimated_tokens for t, _ in pairs)
    total_hc   = sum(h.estimated_tokens for _, h in pairs)
    print(f"Commands used (traditional): {', '.join(sorted(trad_cmds))}")
    print(f"Commands used (hybrid-coco): {', '.join(sorted(hc_cmds))}")

    print_detail(pairs)

    result_path = save_results(pairs, index_stats)
    print(f"\nResults saved to: {result_path}")
    print()


if __name__ == "__main__":
    main()
