# hybrid-coco CLI Reference

## Commands

```
hc index [PATH]          Index PATH (default: cwd). Flag: --exclude PATTERN (repeatable)
hc update [PATH]         Re-index only files with changed sha256. Flag: --exclude PATTERN
hc status [PATH]         Index stats (files, symbols by kind, last update)
hc query <TEXT>          FTS5 search. Flags: --path, --lang (repeatable), --offset, --limit
hc symbol <NAME>         Lookup by name (exact, then prefix). Same filter flags as query
hc file-context <PATH>   All symbols in PATH (relative to cwd). ~97% savings vs cat
hc snippet <PATH> <START> <END>
                         Read PATH lines START..END from disk (1-based, inclusive)
hc structure <KIND>      Structural search: function | method | class | import
hc embed [PATH] --model NAME
                         Build sqlite-vec embeddings. --model is required (no default)
hc semantic <TEXT>       Nearest-neighbour search using the model stored by hc embed
                         Same filter flags as query
hc serve                 Start MCP server (stdio)
hc doctor [PATH]         Diagnostics (index/schema/languages/embeddings extra/MCP/hooks/versions)
hc reset [PATH]          Delete index DB. Flags: -f, --all (also drop project MCP entry)
hc init [PATH]           Index + ensure .hybrid-coco/ in .gitignore + register MCP
```

`.hybrid-coco/config.toml` is created automatically if missing (`hc init`, `hc index`, `hc doctor`). All three keys are required:

```
include = []
exclude = []
languages = {}
```

Edit the file to apply include/exclude/language overrides. `hc reset` keeps `config.toml`. An existing invalid file is not overwritten.

## Index Resolution

- `hc query`, `hc symbol`, `hc file-context`, `hc snippet`, `hc structure`, `hc semantic`, `hc serve`: resolve from `Path.cwd()` — no PATH argument except where shown
- `hc index`, `hc update`, `hc status`, `hc embed`: accept optional PATH argument (default: cwd)

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

### `hc snippet <PATH> <START> <END>`

```
File: src/git.rs:45-67 (23 lines)

pub fn run(args: GitArgs) -> Result<()> {
    ...
}
```

Errors exit non-zero: missing file, empty file, or line range out of bounds.

### `hc structure <KIND>`

```
[pkg/app.py:12] function top_level (python)
  def top_level():
```

`KIND` is one of `function`, `method`, `class`, `import`. Same `--path`, `--lang`, `--offset`, `--limit` filters as `hc query`.

### `hc embed --model NAME`

```
Embedded 312 symbols  model=NAME  dim=384
```

Requires `pip install 'hybrid-coco[vec]'`. `--model` has no default. After `hc index` / `hc update`, embeddings may be stale — run `hc embed` again.

### `hc semantic <TEXT>`

```
[src/tracking.rs:1036]  struct TimedExecution  dist=0.4120 — Records token savings to SQLite
```

Uses the model stored by `hc embed`. Same `--path`, `--lang`, `--offset`, `--limit` filters as `hc query`. Fails if the extra is missing or embeddings have not been built.

## Notes

- Built with Click. Entry point: `hc = "hybrid_coco.cli:main"` in pyproject.toml.
- Plural convention: `hc status` uses correct plurals (`class` → `classes`).
- `hc init` is idempotent — safe to re-run on an already-initialized project.
