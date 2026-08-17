# hybrid-coco — Agent Rules

Reglas para agentes que trabajan en este repositorio. Estado del producto y fases: `ROADMAP.md` (raíz).

---

## Non-negotiable constraints

- SQLite only — no PostgreSQL, no Docker, no always-on server infrastructure
- FTS5 + tree-sitter before any embedding / vector layer
- `pip install hybrid-coco && hc init` must work — two commands, done
- MCP server in the **project** host config (Claude Code: `.claude/settings.json`; Cursor: `.cursor/mcp.json`; Codex: `.codex/config.toml`; OpenCode: `opencode.json`; Devin: `.devin/mcp_config.json`), not desktop-only config
- MCP tool names `hc_*` must never be truncated or renamed
- `.claude/` stays gitignored (local Claude Code settings only; not versioned)

---

## Development conventions

- **Roadmap:** phase status and scope live in `ROADMAP.md`; update the Status column when a phase lands
- **Languages:** new parsers under `src/hybrid_coco/parsers/`, registry in `parsers/__init__.py`, tests in `tests/test_languages.py`, README language table
- **Skills:** Claude Code source of truth `src/hybrid_coco/assets/skills/` — mirror to `skills/` and `plugin/skills/` with `hc sync-skills` (CI enforces `--check`). Host-adapted trees live under `src/hybrid_coco/assets/hosts/<host>/skills/`. Same skill names (`hybrid-coco`, `hc-init`, `hc-search`); bodies match that host's MCP path, native tools, and hook events. `skills_src(host)` has no fallback to Claude.
- **Tests:** `uv run pytest` before merge
- **PR / roadmap text:** English
- **Commits / PRs:** project owner identity (`Jose Meira <90699520+jmeiracorbal@users.noreply.github.com>`) — not the cloud agent default author; use `--no-verify` if hooks inject co-author lines

---

## Release protocol (after every merge to main)

Bump and align versions for package + Claude/plugin surfaces, then tag:

1. Set the same semver in:
   - `pyproject.toml` (`project.version`)
   - `src/hybrid_coco/__init__.py` (`__version__` — `hc --version`)
   - `plugin/.claude-plugin/plugin.json`
   - `.claude-plugin/marketplace.json`
   - `ROADMAP.md` package line
2. Commit on `main` as project owner: `chore: bump version to X.Y.Z`
3. Create and push annotated tag `vX.Y.Z` (triggers PyPI + GitHub Release)

Do this after every landed feature/fix merge that ships to users.

---

## Key paths

| Area | Path |
|------|------|
| CLI | `src/hybrid_coco/cli.py` |
| Indexer | `src/hybrid_coco/indexer.py` |
| MCP server | `src/hybrid_coco/server.py` |
| Agent hosts | `src/hybrid_coco/hosts/` |
| Parsers | `src/hybrid_coco/parsers/` |
| Packaged assets (hooks, awareness, skills) | `src/hybrid_coco/assets/` |
| Host-adapted skills | `src/hybrid_coco/assets/hosts/<host>/skills/` |
| Claude Code plugin | `plugin/` |
| Agent skills (repo mirror) | `skills/` |
