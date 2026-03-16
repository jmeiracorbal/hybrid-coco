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
- **Orchestrator** (Claude, main session): reads `.claude/context/plan.md`, delegates to subagents, saves to Engram
- **Subagents**: implement specific phases — they read Engram context + this file only

Before delegating: check Engram for prior context on that phase.

---

## Non-Negotiable Constraints

- SQLite only — no PostgreSQL, no Docker, no server infrastructure
- FTS5 + tree-sitter before any embedding/vector layer
- `pip install hybrid-coco && hc init` must work — two commands, done
- MCP server configured for Claude Code (`.claude/settings.json`), NOT `claude_desktop_config.json`
- tool names `hc_*` must never be truncated — if using gtk-ai, set `GTK_MCP_PASSTHROUGH_PATTERNS="hc_"`

---

## Context References

- **Roadmap + phase status**: `.claude/context/plan.md`
- **Phase specs and state**: `.claude/context/phases/phase-0X.md`
- **Architecture decisions**: `.claude/context/decisions/adr-XXX.md`
- **Component docs**: `.claude/context/components/`
- **Live progress**: Engram — `mem_search project=hybrid-coco`

---

## Related Components

| Component | Role | Path |
|-----------|------|------|
| gtk-ai | Output compression proxy | https://github.com/jmeiracorbal/gtk-ai |
| CocoIndex (reference) | Indexing pipeline patterns | https://cocoindex.io |
