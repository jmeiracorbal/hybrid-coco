# hybrid-coco — Agent Rules

## Session Protocol (mandatory)

**1. Load context before any work:**
```
mem_context project=hybrid-coco
```

**2. Save after any significant decision:**
```
mem_save title="..." type="decision|architecture|bugfix" project=hybrid-coco
```

**3. Summarize at session end:**
```
mem_session_summary project=hybrid-coco
```

Do NOT put volatile state in this file. Use Engram.

---

## Architect / Orchestrator / Subagent Model

- **Architect** (human): defines phases, reviews, corrects course
- **Orchestrator** (Claude, main session): reads `ROADMAP.md`, delegates to subagents, saves to Engram
- **Subagents**: implement specific phases — they read Engram context + this file only

Before delegating: check Engram for prior context on that phase.

---

## Non-Negotiable Constraints

- SQLite only — no PostgreSQL, no Docker, no server infrastructure
- FTS5 + tree-sitter before any embedding/vector layer
- `pip install hybrid-coco && hc init` must work — two commands, done
- MCP server configured for Claude Code (`.claude/settings.json`), NOT `claude_desktop_config.json`
- tool names `hc_*` must never be truncated — if using gtk-ai, set `GTK_MCP_PASSTHROUGH_PATTERNS="hc_"`
- `.claude/` stays gitignored (local Claude Code settings only; not versioned)

---

## Release protocol (after every merge to main)

Always bump and align versions for package + Claude/agent surfaces, then tag:

1. Set the same semver in:
   - `pyproject.toml` (`project.version`)
   - `src/hybrid_coco/__init__.py` (`__version__` — CLI `hc --version` reads this)
   - `plugin/.claude-plugin/plugin.json`
   - `.claude-plugin/marketplace.json`
   - `ROADMAP.md` package line
2. Commit on `main` as the project owner (never Cursor Agent): `chore: bump version to X.Y.Z`
3. Create and push annotated tag `vX.Y.Z` (triggers PyPI + GitHub Release)

Do this after every landed feature/fix merge that ships to users. Persist the same rule in Engram when available.

---

## Context References

- **Roadmap + phase status**: `ROADMAP.md`
- **Live progress**: Engram — `mem_search project=hybrid-coco`

---

## Related Components

| Component | Role | Path |
|-----------|------|------|
| gtk-ai | Output compression proxy | https://github.com/jmeiracorbal/gtk-ai |
| CocoIndex (reference) | Indexing pipeline patterns | https://cocoindex.io |
