# hybrid-coco

[![CI](https://github.com/jmeiracorbal/hybrid-coco/actions/workflows/ci.yml/badge.svg)](https://github.com/jmeiracorbal/hybrid-coco/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/hybrid-coco.svg)](https://pypi.org/project/hybrid-coco/)
[![PyPI downloads](https://img.shields.io/pypi/dm/hybrid-coco.svg)](https://pypi.org/project/hybrid-coco/)
[![Python](https://img.shields.io/pypi/pyversions/hybrid-coco.svg)](https://pypi.org/project/hybrid-coco/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/jmeiracorbal/hybrid-coco.svg)](https://github.com/jmeiracorbal/hybrid-coco/issues)

Local, self-contained code intelligence for AI agents. Index your codebase once, query it deterministically with the `hc` CLI and `hc_*` MCP tools — one install, no external services.

hybrid-coco ships everything in one component: SQLite storage, tree-sitter parsers, CLI, MCP server, Claude Code hooks, awareness, and agent skills. No embeddings, no vector database, no Docker, no companion tools.

```
pip install hybrid-coco && hc init
```

### The problem it solves

When Claude reads a file to find one function, it pays for the entire file:

```
# Without hybrid-coco
Read("src/gitlab_helpers.py")             >  12,140 tokens  (whole file)

# With hybrid-coco
hc_file_context("src/gitlab_helpers.py")  >  297 tokens  (symbols only)  < 97.6% savings
```

The hook intercepts `Read` and `Grep` calls and suggests the equivalent `hc_*` tool. Same answer, fraction of the tokens.

## How it works

```
Source files  ──tree-sitter──►  SQLite + FTS5  ──►  CLI (hc)
                                     │
                                     └──────────────►  MCP server (hc_*)
                                                           │
                                                    Claude Code hooks
                                                    intercept Read/Grep
                                                    > suggest hc_* tools
```

1. **`hc index .`**: parses every source file with tree-sitter, extracts symbols (functions, classes, methods, imports) with their signatures, docstrings, and line numbers into a FTS5 trigram index
2. **`hc query / symbol / file-context`**: queries the index and returns only what's relevant, not the whole file
3. **`hc serve`**: exposes the same queries as MCP tools (`hc_search`, `hc_symbol`, `hc_file_context`, `hc_status`) for Claude Code
4. **Hooks**: `hc init` registers PreToolUse/PostToolUse hooks that suggest `hc_*` tools whenever Claude is about to `Read` or `Grep` an indexed file

## Benchmark

Measured on a real Rust codebase: 76 files, 2,242 symbols:

| Query | Baseline (full read / shell search) | hybrid-coco | Savings |
|---|---|---|---|
| Symbol lookup (`TimedExecution`) | 2,227 tok | 51 tok | **97.7%** |
| Pattern search (`savings`) | 3,164 tok | 334 tok | **89.4%** |
| File structure (`tracking.rs`) | 12,140 tok | 1,245 tok | **89.7%** |
| Schema grep (`CREATE TABLE`) | 92 tok | 29 tok | 68.5% |
| File read (`git.rs`) | 16,343 tok | 377 tok | **97.7%** |
| **Total (5 queries)** | **33,966 tok** | **2,036 tok** | **~94%** |

Baseline = recursive search plus reading whole files. hybrid-coco = `hc symbol` + `hc query` + `hc file-context`.

## Quickstart

### 1. Install

**Option A: One-line installer (recommended)**

```bash
curl -fsSL https://raw.githubusercontent.com/jmeiracorbal/hybrid-coco/main/install.sh | bash
```

Installs `hc`, configures Claude Code hooks, and adds the awareness file. Requires Python 3.11+ (detects uv, pipx, or pip automatically).

**Option B: Claude Code plugin**

```bash
claude plugin marketplace add jmeiracorbal/hybrid-coco
claude plugin install hybrid-coco@hybrid-coco
```

Registers the MCP server and hooks automatically. Requires `hc` in PATH — install the package first:

```bash
pip install hybrid-coco   # or: uv tool install hybrid-coco
```

### 2. Index your project and register with Claude Code

```bash
cd your-project/
hc init
```

`hc init` does four things:
- Indexes the current directory (tree-sitter, SHA-256 incremental)
- Registers the MCP server in `.claude/settings.json`
- Installs global hooks in `~/.claude/hooks/` that intercept `Read` and `Grep`
- Installs agent skills in `~/.claude/skills/` (`hybrid-coco`, `hc-init`, `hc-search`)

Restart Claude Code to activate.

### 3. Use from Claude Code

The MCP tools are now available in every conversation:

```
hc_search("savings_pct")       # FTS5 search over names, signatures, docstrings
hc_symbol("TimedExecution")    # exact/prefix symbol lookup
hc_file_context("src/git.rs")  # all symbols in a file, structured
hc_status()                    # index stats
```

Invocable skills: `/hc-init` (setup/repair without full-reindex storms), `/hc-search` (choose the right `hc_*` query). The main `hybrid-coco` skill covers when to prefer `hc_*` over Read/Grep.

The hooks will remind you (via stderr) whenever Claude is about to read an indexed file directly.

## CLI reference

```
hc index [PATH] [--exclude PATTERN]...
                         Index PATH (default: cwd); optional exclude patterns
hc update [PATH] [--exclude PATTERN]...
                         Re-index only changed files (SHA-256 diff)
hc status [PATH]         Index stats: files, symbols by kind, last update
hc query <TEXT> [--path P] [--lang L]... [--offset N] [--limit N]
                         FTS5 search; optional path/lang filters and pagination
hc symbol <NAME> [--path P] [--lang L]... [--offset N] [--limit N]
                         Exact name lookup, then prefix; same filters as query
hc file-context <PATH>   All symbols in PATH grouped by kind (~97% savings vs cat)
hc doctor [PATH]         Diagnostics: index, schema, languages, MCP/hooks, versions
hc reset [PATH] [-f] [--all]
                         Delete index DB; --all also drops project MCP entry
hc serve                 Start MCP server (stdio)
hc init [PATH]           Index + .gitignore entry + register MCP + install hooks
```

`--exclude` accepts gitignore-style patterns and may be repeated.

## Supported languages

| Language | Parser |
|---|---|
| Python | tree-sitter-python |
| Rust | tree-sitter-rust |
| JavaScript | tree-sitter-javascript |
| TypeScript | tree-sitter-typescript |
| Go | tree-sitter-go |
| Java | tree-sitter-java |
| C | tree-sitter-c |
| C++ | tree-sitter-cpp |
| C# | tree-sitter-c-sharp |
| Kotlin | tree-sitter-kotlin |
| Swift | tree-sitter-swift |

Adding a language requires implementing a ~100-line parser in `src/hybrid_coco/parsers/`.

## Design decisions

**SQLite + FTS5, not a vector database**: deterministic results, zero infrastructure, single file. Trigram search covers partial matches and is fast enough for codebases up to ~100K files. Semantic (embedding) search can be layered on top via `sqlite-vec` without changing the schema.

**tree-sitter, not regex**: symbol extraction is grammar-aware. Signatures and docstrings are extracted structurally, not by pattern matching.

**No server process**: `hc serve` runs as a stdio MCP server launched on demand by Claude Code. There is no daemon to manage.

**Incremental by default**: `hc update` re-indexes only files whose SHA-256 has changed. Full re-index is only needed on first run or after `.gitignore` changes.

## Boundaries

hybrid-coco is a single local component:

- SQLite storage in the project workspace
- tree-sitter parsers for symbol extraction
- CLI (`hc`) for indexing and querying
- MCP server (`hc_*`) for Claude Code
- hooks, awareness, and skills shipped with the package

It does not require companion services, external proxies, background daemons, or additional infrastructure.

## Development

```bash
git clone https://github.com/jmeiracorbal/hybrid-coco
cd hybrid-coco
uv sync
uv pip install -e .
hc --version
```

Run tests:

```bash
uv run pytest
```

Run the benchmark against any indexed project:

```bash
cd path/to/project && hc index .
python scripts/benchmark.py path/to/project
```
