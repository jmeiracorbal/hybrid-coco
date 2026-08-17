# hybrid-coco — Roadmap

Status: **active** · Last updated: 2026-08-17 · Package: `0.2.0`

## Goal

Local, deterministic code intelligence for AI agents: index once with tree-sitter into SQLite + FTS5, query via CLI and `hc_*` MCP tools, and intercept wasteful `Read`/`Grep` with host-native hooks. Two commands must remain enough: `pip install hybrid-coco && hc init`. Extra hosts opt in with `hc init --host <name>`.

## Non-negotiable constraints

- SQLite only — no PostgreSQL, no Docker, no always-on server process
- FTS5 + tree-sitter **before** any embedding / vector layer
- MCP registered in the **project** host config (Claude Code: `.claude/settings.json`; Cursor: `.cursor/mcp.json`; Codex: `.codex/config.toml`; OpenCode: `opencode.json`; Devin: `.devin/mcp_config.json`), not desktop-only config
- Tool names `hc_*` are part of the public interface and must remain stable
- `hc init` default host remains Claude Code; additional hosts are explicit `--host` values
- Skills keep the same names (`hybrid-coco`, `hc-init`, `hc-search`) on every host; `SKILL.md` bodies are host-adapted. Hooks use only events that host actually supports

## Current baseline (done)

| Area | State |
|------|--------|
| Indexer | Incremental SHA-256 walk, gitignore-aware, `.hybrid-coco/config.toml` + CLI `--exclude` |
| Store | SQLite files + symbols + FTS5 trigram |
| Languages | Python, JavaScript, TypeScript/TSX, Rust, Go, Java, C, C++, C#, Kotlin, Swift |
| CLI | `index`, `update`, `status`, `query`, `symbol`, `file-context`, `snippet`, `structure`, `serve`, `doctor`, `reset`, `init`, `hook`, `install-instructions`, `sync-skills` (maintainers) |
| MCP | `hc_search`, `hc_symbol`, `hc_file_context`, `hc_snippet`, `hc_structure`, `hc_status` (path/lang/offset/limit on search, symbol & structure) |
| Hosts | Claude Code (default); Cursor; Codex; OpenCode; Devin |
| Skills | Host-adapted `hybrid-coco` / `hc-init` / `hc-search`; Claude mirrors synced via `hc sync-skills` |
| Architecture | Shared `query` + `formatters` layer; unified `languages/registry.py`; `parsers/ts_utils.py`; `hosts/base.py` + `hooks_patch.py` |
| Awareness | mnemo split: `install.sh` / `hc install-instructions` writes a short conditional gate in user-global instruction files. `hc init` only writes `.hybrid-coco/project.json` + protocol `.hybrid-coco/hybrid-coco.md`. A present marker with a missing/invalid `id` is rewritten to the path uuid5; missing marker or missing `version`/`agents` stays inactive. No project `AGENTS.md` / `CLAUDE.md` |
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
| 11 | Codex host (MCP, skills, hooks) | **done** |
| 12 | OpenCode host (MCP, skills, hooks) | **done** |
| 13 | Devin host (MCP, skills, hooks) | **done** |
| 14 | Internal architecture (DRY refactor) | **done** |
| 15 | Skill mirror automation | **done** |

---

## Phase 14 — Internal architecture (DRY refactor)

**Why:** CLI, MCP, and hooks duplicated query orchestration and output formatting; language and host knowledge was scattered.

**Done:**

- `query.py` + `formatters.py` — single application layer for CLI, MCP, and hook surfaces
- `languages/registry.py` — extensions, tree-sitter loaders, parser factories, structure queries
- `parsers/ts_utils.py` — shared tree-sitter helpers
- `hosts/base.py` + `hooks_patch.py` — shared MCP registration, skill install, hook patching

**Exit criteria:** no behavior change; snapshot tests assert output parity across surfaces.

---

## Phase 15 — Skill mirror automation

**Why:** Claude skills in `assets/skills/` must stay aligned with repo mirrors `skills/` and `plugin/skills/`.

**Done:** `hc sync-skills` copies mirrors from packaged assets; `hc sync-skills --check` and pytest enforce parity in CI.

**Exit criteria:** editing `assets/skills/` without syncing fails CI; one command refreshes both mirrors.

---

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
