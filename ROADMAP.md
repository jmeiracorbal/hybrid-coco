# hybrid-coco — Roadmap

Status: **active** · Last updated: 2026-08-17 · Package: `0.1.16`

## Goal

Local, deterministic code intelligence for AI agents: index once with tree-sitter into SQLite + FTS5, query via CLI and `hc_*` MCP tools, and intercept wasteful `Read`/`Grep` with host-native hooks. Two commands must remain enough: `pip install hybrid-coco && hc init`. Extra hosts opt in with `hc init --host <name>`.

## Non-negotiable constraints

- SQLite only — no PostgreSQL, no Docker, no always-on server process
- FTS5 + tree-sitter **before** any embedding / vector layer
- MCP registered in the **project** host config (Claude Code: `.claude/settings.json`; Cursor: `.cursor/mcp.json`), not desktop-only config
- Tool names `hc_*` are part of the public interface and must remain stable
- `hc init` default host remains Claude Code; additional hosts are explicit `--host` values
- Skills are the same packaged `SKILL.md` set on every host; hooks use only events that host actually supports

## Current baseline (done)

| Area | State |
|------|--------|
| Indexer | Incremental SHA-256 walk, gitignore-aware, `.hybrid-coco/config.toml` + CLI `--exclude` |
| Store | SQLite files + symbols + FTS5 trigram |
| Languages | Python, JavaScript, TypeScript/TSX, Rust, Go, Java, C, C++, C#, Kotlin, Swift |
| CLI | `index`, `update`, `status`, `query`, `symbol`, `file-context`, `snippet`, `structure`, `serve`, `doctor`, `reset`, `init`, `hook` |
| MCP | `hc_search`, `hc_symbol`, `hc_file_context`, `hc_snippet`, `hc_structure`, `hc_status` (path/lang/offset/limit on search, symbol & structure) |
| Hosts | Claude Code (default `hc init`); Cursor (`hc init --host cursor`) |
| Hooks | Host-native intercept of Read/Grep (or equivalent) → `hc_*`; write/edit → `hc update`; session start incremental update where the host has the event |
| Packaging | PyPI, `install.sh`, Claude Code plugin marketplace |

## Phase overview

| Phase | Title | Status |
|-------|--------|--------|
| 01 | Index hygiene & CLI completeness | **done** |
| 02 | Query filters (path, language, pagination) | **done** |
| 03 | Doctor, reset, version alignment | **done** |
| 04 | Language coverage (Go, Java, then C/C++) | **done** |
| 05 | Agent skill owns lifecycle | **done** |
| 06 | Symbol body / targeted snippet | **done** |
| 07 | Structural search (tree-sitter patterns) | **done** |
| 08 | Settings file (include / exclude) | **done** |
| 09 | Embeddings optional layer (`sqlite-vec`) | deferred |
| 10 | Cursor host (MCP, skills, hooks) | **done** |
| 11 | Codex host (MCP, skills, hooks) | pending |
| 12 | OpenCode host (MCP, skills, hooks) | pending |
| 13 | Devin host (MCP, skills, hooks) | pending |

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

**Done:** `hc snippet` CLI + `hc_snippet` MCP; explicit errors for missing files and out-of-range lines; awareness/skills/hooks recommend snippet over full-file Read when line ranges are known.

**Exit criteria:** MCP + CLI can return a bounded code slice; out-of-range / missing file fail explicitly; hooks/awareness recommend snippet over full-file Read when lines are known.

---

## Phase 07 — Structural search (later)

Tree-sitter query / by-example patterns over the working tree (or indexed ASTs), without embeddings. Useful when FTS keywords fail but shape is known (`fn …`, `class …`). Depends on solid multi-language parsers (phase 04).

**Done:** `hc structure KIND` CLI + `hc_structure` MCP over indexed files; kinds `function`, `method`, `class`, `import`; optional `path`/`lang`/pagination filters; per-language tree-sitter queries.

## Phase 08 — Settings file (later)

Project-level include/exclude / language overrides in `.hybrid-coco/config.toml`. The file is always created on `hc init` / `hc index` with explicit empty lists; all keys are required.

**Done:** `.hybrid-coco/config.toml` (`include`, `exclude`, `languages`) is written if missing (index/init/doctor self-heal); load reads the file after create; invalid existing files fail and are not overwritten; CLI `--exclude` still applies; `hc reset` keeps the config file.

## Phase 09 — Embeddings optional layer (deferred)

Only after FTS5 + tree-sitter path is complete. Candidate: optional `sqlite-vec` extra. Must not become a required dependency or break deterministic CLI defaults.

## Phase 10 — Cursor host

**Why:** Cursor is an MCP client with Agent Skills and a smaller hook surface than Claude Code. Cloud agents only load **project** `.cursor/` hooks.

**Done:** `hc init --host cursor` (and `--host all`) registers:

| Surface | Location | Behavior |
|---------|----------|----------|
| MCP | `.cursor/mcp.json` (`~/.cursor/mcp.json` with `--global`) | `hc serve` stdio, same `hc_*` names |
| Skills | `.cursor/skills/` + `~/.cursor/skills/` | same packaged `hybrid-coco`, `hc-init`, `hc-search` |
| Hooks | `.cursor/hooks.json` | `preToolUse` Read\|Grep, `beforeReadFile`, `postToolUse` Write\|StrReplace, `afterFileEdit`, `sessionStart` via `hc hook cursor <event>` |

Cursor cannot clone every Claude Code matcher; intercept uses the events Cursor actually fires. Output is Cursor JSON (`permission: deny` + `agent_message`), not Claude `decision: block`.

**Exit criteria:** init is idempotent; skills bytes match packaged assets; hook tests block indexed Read/Grep and pass unindexed files; `hc reset --all` drops the Cursor MCP entry.

## Phase 11 — Codex host

**Why:** Codex CLI/IDE shares the Agent Skills standard and MCP via `.codex/config.toml`, but has no Read/Grep tools — file reads go through `Bash` / `apply_patch`.

**Scope:**

- MCP: `[mcp_servers.hybrid-coco]` in `.codex/config.toml`
- Skills: `.agents/skills/` + `~/.agents/skills/` (same `SKILL.md` set)
- Hooks: `.codex/hooks.json` — `PreToolUse` on `Bash` (simple `cat`/`head`/`rg`/`grep` of indexed files), `PostToolUse` on `apply_patch`/`Edit`/`Write` → `hc update`, `SessionStart` additionalContext
- Do not invent Claude-only events Codex does not fire

**Exit criteria:** init + doctor + reset cover Codex; hook tests intercept a `cat` of an indexed file and refresh on `apply_patch`; skills match packaged assets.

## Phase 12 — OpenCode host

**Why:** OpenCode loads MCP from `opencode.json`, skills from `.opencode/skills/`, and hooks as JS plugins (`tool.execute.before` / `tool.execute.after`), not Claude `settings.json`.

**Scope:**

- MCP: `opencode.json` `mcp.hybrid-coco` local command `["hc", "serve"]`
- Skills: `.opencode/skills/` + `~/.config/opencode/skills/`
- Plugin: `.opencode/plugins/hybrid-coco.js` calling `hc hook opencode …` for `read`/`grep` before and `write`/`edit` after
- OpenCode tool args use `filePath` — no silent aliasing to Claude `file_path`

**Exit criteria:** init writes plugin + MCP + skills; Python hook tests block `read` with `filePath`; skills match packaged assets.

## Phase 13 — Devin host

**Why:** Devin CLI is Claude-hook-compatible (`.devin/hooks.v1.json`) with its own MCP file and skill directories.

**Scope:**

- MCP: `.devin/mcp_config.json`
- Skills: `.devin/skills/` + `~/.config/devin/skills/`
- Hooks: `.devin/hooks.v1.json` — `PreToolUse` `read|grep`, `PostToolUse` `write|edit`, `SessionStart`
- Tool names are lowercase (`read`, `grep`); matchers are regex as Devin documents

**Exit criteria:** init + doctor + reset cover Devin; hook tests use Devin `decision: block` shape; skills match packaged assets.

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
