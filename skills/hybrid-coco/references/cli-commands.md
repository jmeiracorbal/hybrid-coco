# hybrid-coco CLI Reference

## Commands

```
hc index [PATH]          Index PATH (default: cwd). Flag: --exclude PATTERN
hc update [PATH]         Re-index only files with changed sha256
hc status [PATH]         Index stats (files, symbols by kind, last update)
hc query <TEXT>          FTS5 search on name, signature, docstring
hc symbol <NAME>         Lookup by name (exact, then prefix fallback)
hc file-context <PATH>   All symbols in PATH (relative to cwd). ~97% savings vs cat
hc serve                 Start MCP server (stdio)
hc init [PATH]           Index + register MCP in .claude/settings.json
```

## Index Resolution

- `hc query`, `hc symbol`, `hc file-context`, `hc serve`: resolve index from `Path.cwd()` — no PATH argument accepted
- `hc index`, `hc update`, `hc status`: accept optional PATH argument (default: cwd)

Always run `hc query` and `hc symbol` from inside the indexed project root.

## Output Format

Output is compact and LLM-agent-optimized. Results fit within 500 tokens.

### `hc status`

```
Index: .hybrid-coco/index.db
Files:   47 indexed
Symbols: 312 (187 functions, 23 classes, 102 imports)
Updated: 2026-03-12 15:42
```

### `hc symbol <NAME>`

```
function run @ src/git.rs:45-67
  sig: pub fn run(args: GitArgs) -> Result<()>
  doc: Executes git command with token-optimized output
```

### `hc query <TEXT>`

```
[src/tracking.rs:1036] struct TimedExecution — Records token savings to SQLite
[src/git.rs:45]        function run — Executes git command with token-optimized output
```

### `hc file-context <PATH>`

```
File: src/tracking.rs (rust) — 42 symbols

Structs (5):
  Tracker @ 92
  CommandRecord @ 100
  GainSummary @ 116
  TimedExecution @ 1036

Functions (18):
  new @ 247  pub fn new() -> Result<Self>
  record @ 343  pub fn record(...) -> Result<()>
  ...
```

## Notes

- Built with Click. Entry point: `hc = "hybrid_coco.cli:main"` in pyproject.toml.
- Plural convention: `hc status` uses correct plurals (`class` → `classes`).
- `hc init` is idempotent — safe to re-run on an already-initialized project.
