---
name: hc-init
description: Initialize or repair hybrid-coco in this project — install, index if missing, register MCP/hooks. Prefer over full reindex when an index already exists.
user-invokable: true
---

# hc-init

Own the hybrid-coco lifecycle for the current project. Prefer the smallest action that restores a working index + MCP wiring.

## Rules (anti-storm)

- If `.hybrid-coco/index.db` **exists**, do **not** run `hc index` unless the user asked for a full rebuild or `hc doctor` / a failed query made that necessary after `hc reset`.
- SessionStart / PostToolUse may already run `hc update`. Do not stack a full reindex on top.
- Prefer `hc update .` for staleness; prefer `hc doctor` for diagnosis.

## Procedure

### 1. Binary present?

```bash
hc --version
```

If missing: tell the user to run `pip install hybrid-coco` (or the project install path). Stop until `hc` works.

### 2. Index missing?

Look for `.hybrid-coco/index.db` at the project root.

If **missing**:

```bash
hc init .
```

Then report: files/symbols indexed, index path, that Claude Code may need a restart to load MCP.

If **present**: skip `hc init` unless MCP/hooks are clearly unregistered (see step 4).

### 3. Stale or empty?

```bash
hc status .
```

- Files/symbols look wrong after edits → `hc update .`
- Suspect corruption → `hc doctor .`
- User wants a wipe → `hc reset -f` (add `--all` only if they also want the project MCP entry removed), then `hc init .`

### 4. MCP / hooks

If `hc_status` / `hc_*` tools are unavailable after an index exists:

```bash
hc init .
```

`hc init` is idempotent: re-registers MCP in `.claude/settings.json`, refreshes global awareness/hooks/skills under `~/.claude/`. Restart Claude Code if MCP was newly registered.

### 5. Report

Always report what you ran and the outcome (`hc status` summary, or doctor failures). Do not claim the index is ready without evidence from status/doctor.
