# hybrid-coco — Roadmap

Status: **active** · Last updated: 2026-08-17 · Package: `0.1.13`

## Goal

Local, deterministic code intelligence for AI agents: index once with tree-sitter into SQLite + FTS5, query via CLI and `hc_*` MCP tools, and intercept wasteful `Read`/`Grep` with Claude Code hooks. Two commands must remain enough: `pip install hybrid-coco && hc init`.

## Non-negotiable constraints

- SQLite only — no PostgreSQL, no Docker, no always-on server process
- FTS5 + tree-sitter **before** any embedding / vector layer
- MCP registered in `.claude/settings.json` (Claude Code), not desktop config
- Tool names `hc_*` are part of the public interface and must remain stable

## Current baseline (done)

| Area | State |
|------|--------|
| Indexer | Incremental SHA-256 walk, gitignore-aware, `--exclude` patterns |
| Store | SQLite files + symbols + FTS5 trigram |
| Languages | Python, JavaScript, TypeScript/TSX, Rust, Go, Java, C, C++, C#, Kotlin, Swift |
| CLI | `index`, `update`, `status`, `query`, `symbol`, `file-context`, `serve`, `doctor`, `reset`, `init` |
| MCP | `hc_search`, `hc_symbol`, `hc_file_context`, `hc_status` (path/lang/offset/limit on search & symbol) |
| Hooks | Blocking PreToolUse (Read/Grep → hc), PostToolUse, SessionStart awareness + incremental update |
| Packaging | PyPI, `install.sh`, Claude Code plugin marketplace |

## Phase overview

| Phase | Title | Status |
|-------|--------|--------|
| 01 | Index hygiene & CLI completeness | **done** |
| 02 | Query filters (path, language, pagination) | **done** |
| 03 | Doctor, reset, version alignment | **done** |
| 04 | Language coverage (Go, Java, then C/C++) | **done** |
| 05 | Agent skill owns lifecycle | **done** |
| 06 | Symbol body / targeted snippet | **next** |
| 07 | Structural search (tree-sitter patterns) | later |
| 08 | Settings file (include / exclude) | later |
| 09 | Embeddings optional layer (`sqlite-vec`) | deferred |

---

## Phase 01 — Index hygiene & CLI completeness

**Why:** advertised flags and init behavior must match reality; index dir must not leak into git.

- Wire `--exclude` on `hc index` / `hc update` (patterns currently accepted but unused)
- On `hc init`, ensure `.hybrid-coco/` is listed in the project `.gitignore`
- SessionStart (or equivalent) can trigger `hc update` when an index already exists
- Keep stdout/stderr contract stable for hooks and MCP

**Exit criteria:** exclude patterns affect indexed set; fresh `hc init` leaves `.hybrid-coco/` ignored; no regression on existing MCP tools.

---

## Phase 02 — Query filters

**Why:** agents often need “search only under `src/`” or “only Python” without drowning in noise.

- CLI: `--path`, `--lang` (repeatable), `--offset` / `--limit` on `hc query` (and MCP `hc_search`)
- Apply the same filters to `hc_symbol` where meaningful (path/lang)
- Document filter semantics in skill / awareness file

**Exit criteria:** filtered queries return only matching rows; MCP schemas expose the new parameters; tests cover path + lang + pagination.

---

## Phase 03 — Doctor, reset, version alignment

**Why:** operators and agents need a single health check and a clean wipe path; version drift confuses installs.

- `hc doctor` — index present, schema readable, languages detected, MCP/hooks registration hints
- `hc reset` — delete index DB (optional wipe of local settings); confirmation unless `-f`
- Single source of truth for version: package, `hc --version`, plugin `marketplace.json` / `plugin.json`

**Exit criteria:** doctor exits non-zero on broken index; reset leaves a reproducible empty state; all surfaced versions match.

---

## Phase 04 — Language coverage

**Why:** many agent workloads are Go/Java/C++; unsupported files are invisible to `hc_*`.

Priority order:

1. Go
2. Java
3. C / C++ (headers included)

Each language: tree-sitter grammar dependency, `~100`-line parser extracting functions/types/methods/imports with signatures + docs where the grammar allows, registry entry, tests on fixtures.

**Exit criteria:** fixtures parse; `hc index` counts symbols for the new extensions; README language table updated.

---

## Phase 05 — Agent skill owns lifecycle

**Why:** the agent should init/index/search without asking the user to run shell steps first.

- Skill instructs: if index missing → `hc init` / `hc index`; if stale after edits → `hc update`; then use `hc_*` / CLI
- Align plugin skill + packaged assets skill
- Keep Claude Code as primary host; do not weaken `hc_*` naming

**Done:** main skill `hybrid-coco` (policy) + invocable `hc-init` / `hc-search` (lifecycle/query); packaged under `assets/skills`, mirrored in `plugin/skills` and repo `skills/`; `hc init` installs to `~/.claude/skills/`. SessionStart/`hc update` remain incremental — skills must not trigger full reindex storms.

**Exit criteria:** skill text is actionable end-to-end; SessionStart + skill do not fight each other (no double full reindex storms).

---

## Phase 06 — Symbol body / targeted snippet

**Why:** after `hc_file_context` / `hc_symbol`, agents still need a cheap way to read only the matched range.

Preferred design: query-time disk read via `hc_snippet(path, line_start, line_end)` (CLI + MCP). Do not store full file bodies in SQLite by default.

**Exit criteria:** MCP + CLI can return a bounded code slice; out-of-range / missing file fail explicitly; hooks/awareness recommend snippet over full-file Read when lines are known.

---

## Phase 07 — Structural search (later)

Tree-sitter query / by-example patterns over the working tree (or indexed ASTs), without embeddings. Useful when FTS keywords fail but shape is known (`fn …`, `class …`). Depends on solid multi-language parsers (phase 04).

## Phase 08 — Settings file (later)

Project-level include/exclude / language overrides (e.g. YAML under `.hybrid-coco/`), replacing ad-hoc CLI-only excludes. Must remain optional — defaults keep `pip install && hc init` zero-config.

## Phase 09 — Embeddings optional layer (deferred)

Only after FTS5 + tree-sitter path is complete. Candidate: optional `sqlite-vec` extra. Must not become a required dependency or break deterministic CLI defaults.

---

## Explicitly out of scope (for now)

- Always-on background daemon
- Docker / remote server deployment
- Required cloud APIs or mandatory embedding models
- Renaming or truncating `hc_*` tools

## Working agreement

- Architect (human) prioritizes and accepts phase exit criteria
- Update this file’s phase **Status** column when a phase lands
- PR descriptions and roadmap text: English
- Commits / PRs: project owner identity — never the cloud agent default author
