---
name: hybrid-coco
description: Local code intelligence for deterministic codebase navigation. Index once, query always — use hc_* tools instead of reading files.
---

# hybrid-coco

## Overview

hybrid-coco provides a local SQLite-backed index of your codebase, exposing it through MCP tools (`hc_*`) so that Claude can navigate code deterministically — without reading files blindly or running expensive recursive greps.

**Core principle:** Index once, query always. The `hc_*` MCP tools are cheaper, faster, and more precise than Read + Grep on source files.

**Supported languages:** Python, JavaScript/TypeScript, Rust.

---

## Section 1 — Setup Verification

Before using any `hc_*` tool, verify that hybrid-coco is available and the index exists.

### Step 1: Check `hc` is installed

```bash
hc --version
```

If the command is not found:

```
pip install hybrid-coco
```

### Step 2: Check for an index in the current project

Look for `.hybrid-coco/index.db` in the project root. If it does not exist, initialize:

```bash
hc init .
```

`hc init` does three things in one command: indexes the project, registers the MCP server in `.claude/settings.json`, and installs git hooks (if applicable).

### Step 3: Verify the MCP server is running

Call `hc_status()`. If it fails or the tool is unavailable, start the server:

```bash
hc serve
```

Run this from the project root (where `.hybrid-coco/index.db` lives). The server runs over stdio and is managed by Claude Code once registered.

---

## Section 2 — When to Use Each Tool

**Rule:** Before using Read or Grep on source files, always try the corresponding `hc_*` tool first.

| Situation | Tool to use | Instead of... |
|---|---|---|
| Find a function or class by name | `hc_symbol("name")` | Read + grep |
| Search by concept or keyword | `hc_search("query")` | Recursive grep |
| Understand what is in a file | `hc_file_context("path/to/file")` | Read of the full file |
| Check index health and coverage | `hc_status()` | ls / find |

### Tool details

**`hc_symbol(name: str)`**
Exact lookup by symbol name, with prefix fallback. Returns location, signature, and docstring.
Use when you know the name of a function, class, or variable you are looking for.

**`hc_search(query: str, limit?: int = 20)`**
FTS5 full-text search over name, signature, and docstring fields. Use when you have a concept or keyword but not the exact name.

**`hc_file_context(path: str)`**
Returns all symbols in a file grouped by kind (functions, classes, imports), with line numbers and signatures. Use this before reading a file — it gives structural context in a fraction of the tokens.

**`hc_status()`**
Returns index stats: files indexed, symbol counts by kind, last update time, detected languages. Use to verify the index is current before starting work on a project.

---

## Section 3 — CLI Commands (quick reference)

For full details, see `references/cli-commands.md`.

| Command | What it does |
|---|---|
| `hc index [path]` | Index a project (full scan) |
| `hc update [path]` | Re-index only files with changed sha256 |
| `hc status [path]` | Show index stats |
| `hc query <text>` | FTS5 search from the terminal |
| `hc symbol <name>` | Symbol lookup from the terminal |
| `hc serve` | Start the MCP server (stdio) |
| `hc init [path]` | Index + register MCP + install hooks |

**Index resolution:** `hc query`, `hc symbol`, and `hc serve` resolve the index from `cwd` — always run them from the project root.

---

## Section 4 — Troubleshooting

**MCP tools (`hc_*`) are not available**
The MCP server is not running or not registered. From the project root:
```bash
hc serve
```
If it was never registered, run `hc init .` first.

**Index is stale (symbols not found, results outdated)**
Re-index only changed files:
```bash
hc update .
```
For a full re-index, run `hc index .`.

**`hc_symbol` returns nothing for a symbol that exists**
The file may not be in a supported language. hybrid-coco indexes Python, JavaScript/TypeScript, and Rust. For other languages, fall back to Grep.

**`hc serve` exits immediately**
No index found in cwd. Run `hc index .` first, then `hc serve`.

**Results are truncated by a compression tool**
The `hc_*` tools are designed to return minimal output. If truncation occurs, use a more specific query or request fewer results with the `limit` parameter. If you use gtk-ai alongside hybrid-coco, add `hc_` to `GTK_MCP_PASSTHROUGH_PATTERNS` to prevent compression of `hc_*` responses.

---

## Reference Documentation

- `references/cli-commands.md` — Full CLI reference with output format examples
- `references/mcp-tools.md` — MCP tool signatures, response formats, and usage examples
