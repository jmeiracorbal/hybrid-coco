# hybrid-coco

[![CI](https://github.com/jmeiracorbal/hybrid-coco/actions/workflows/ci.yml/badge.svg)](https://github.com/jmeiracorbal/hybrid-coco/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/hybrid-coco.svg)](https://pypi.org/project/hybrid-coco/)
[![PyPI downloads](https://img.shields.io/pypi/dm/hybrid-coco.svg)](https://pypi.org/project/hybrid-coco/)
[![Python](https://img.shields.io/pypi/pyversions/hybrid-coco.svg)](https://pypi.org/project/hybrid-coco/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/jmeiracorbal/hybrid-coco.svg)](https://github.com/jmeiracorbal/hybrid-coco/issues)

Local code intelligence for AI agents. Index your codebase once, query it deterministically: **~94% fewer tokens** than grep + cat.

hybrid-coco builds a local SQLite index of your source code using tree-sitter, exposes it via a CLI and an MCP server, and integrates with Claude Code via hooks. No embeddings, no vector database, no Docker. One install command.

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

| Query | Traditional | hybrid-coco | Savings |
|---|---|---|---|
| Symbol lookup (`TimedExecution`) | 2,227 tok | 51 tok | **97.7%** |
| Pattern search (`savings`) | 3,164 tok | 334 tok | **89.4%** |
| File structure (`tracking.rs`) | 12,140 tok | 1,245 tok | **89.7%** |
| Schema grep (`CREATE TABLE`) | 92 tok | 29 tok | 68.5% |
| File read (`git.rs`) | 16,343 tok | 377 tok | **97.7%** |
| **Total (5 queries)** | **33,966 tok** | **2,036 tok** | **~94%** |

Traditional = `grep -rn` + `cat`. hybrid-coco = `hc symbol` + `hc query` + `hc file-context`.

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

`hc init` does three things:
- Indexes the current directory (tree-sitter, SHA-256 incremental)
- Registers the MCP server in `.claude/settings.json`
- Installs global hooks in `~/.claude/hooks/` that intercept `Read` and `Grep`

Restart Claude Code to activate.

### 3. Use from Claude Code

The MCP tools are now available in every conversation:

```
hc_search("savings_pct")       # FTS5 search over names, signatures, docstrings
hc_symbol("TimedExecution")    # exact/prefix symbol lookup
hc_file_context("src/git.rs")  # all symbols in a file, structured
hc_status()                    # index stats
```

The hooks will remind you (via stderr) whenever Claude is about to read an indexed file directly.

## CLI reference

```
hc index [PATH]          Index PATH (default: cwd)
hc update [PATH]         Re-index only changed files (SHA-256 diff)
hc status [PATH]         Index stats: files, symbols by kind, last update
hc query <TEXT>          FTS5 trigram search on name, signature, docstring
hc symbol <NAME>         Exact name lookup, then prefix fallback
hc file-context <PATH>   All symbols in PATH grouped by kind (~97% savings vs cat)
hc serve                 Start MCP server (stdio)
hc init [PATH]           Index + register MCP + install hooks
```

## Supported languages

| Language | Parser |
|---|---|
| Python | tree-sitter-python |
| Rust | tree-sitter-rust |
| JavaScript | tree-sitter-javascript |
| TypeScript | tree-sitter-typescript |

Adding a language requires implementing a ~100-line parser in `src/hybrid_coco/parsers/`.

## Design decisions

**SQLite + FTS5, not a vector database**: deterministic results, zero infrastructure, single file. Trigram search covers partial matches and is fast enough for codebases up to ~100K files. Semantic (embedding) search can be layered on top via `sqlite-vec` without changing the schema.

**tree-sitter, not regex**: symbol extraction is grammar-aware. Signatures and docstrings are extracted structurally, not by pattern matching.

**No server process**: `hc serve` runs as a stdio MCP server launched on demand by Claude Code. There is no daemon to manage.

**Incremental by default**: `hc update` re-indexes only files whose SHA-256 has changed. Full re-index is only needed on first run or after `.gitignore` changes.

## Using with gtk-ai

hybrid-coco and [gtk-ai](https://github.com/jmeiracorbal/gtk-ai) are independent tools that work well together:

- **hybrid-coco**: reduces tokens on *code navigation* (`Read`, `Grep`, file structure queries)
- **gtk-ai**: reduces tokens on *command output* (`find`, `ls`, `git`, `grep` and other Bash tools)

When used together, gtk-ai will by default compress all MCP tool output, including `hc_*` responses. To prevent that, add `hc_` to `GTK_MCP_PASSTHROUGH_PATTERNS` in the gtk-ai hook script:

```bash
# ~/.claude/hooks/gtkai-post-tool-use.sh
export GTK_MCP_PASSTHROUGH_PATTERNS="hc_"
```

This tells gtk-ai to let `hc_search`, `hc_symbol`, `hc_file_context`, and `hc_status` responses through uncompressed. hybrid-coco already returns minimal output, so compressing it further would lose information.

Neither tool requires the other. Configure this only if you have both installed.

## Relation to CocoIndex

hybrid-coco is inspired by [CocoIndex](https://cocoindex.io) but makes different trade-offs:

| | CocoIndex | hybrid-coco |
|---|---|---|
| Search | Vector (semantic) | FTS5 trigram (lexical) |
| Backend | PostgreSQL + pgvector | SQLite (single file) |
| Infrastructure | Docker required | Zero |
| Install | Complex | `curl ... | bash && hc init` |
| Granularity | Chunks | Symbols (functions, classes) |
| Target | Large-scale RAG | Local dev, agent token reduction |

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
