---
name: hc-init
description: Initialize or repair hybrid-coco for Devin — index if missing, register .devin MCP/hooks/skills. Prefer over full reindex when an index already exists.
user-invokable: true
---

# hc-init (Devin)

Own the hybrid-coco lifecycle for this Devin project. Prefer the smallest action that restores a working index + MCP wiring.

## Rules (anti-storm)

- If `.hybrid-coco/index.db` **exists**, do **not** run `hc index` unless the user asked for a full rebuild or `hc doctor` / a failed query made that necessary after `hc reset`.
- Devin `SessionStart` / `PostToolUse` may already run `hc update`. Do not stack a full reindex on top.
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
hc init . --host devin
```

Then report: files/symbols indexed, index path, that Devin may need a restart to load MCP from `.devin/mcp_config.json`.

If **present**: skip `hc init` unless MCP/hooks are clearly unregistered (see step 4).

### 3. Stale or empty?

```bash
hc status .
```

- Files/symbols look wrong after edits → `hc update .`
- Suspect corruption → `hc doctor .`
- User wants a wipe → `hc reset -f` (add `--all` only if they also want the project MCP entry removed), then `hc init . --host devin`

### 4. MCP / hooks

If `hc_status` / `hc_*` tools are unavailable after an index exists:

```bash
hc init . --host devin
```

Confirm `.devin/mcp_config.json` has `hybrid-coco`, `.devin/hooks.v1.json` is the hooks object itself (no wrapper `hooks` key) with matchers `^(read|grep)$` and `^(write|edit)$`, and skills exist under `.devin/skills/`. Restart Devin if MCP was newly registered.

Default `hc init` (no `--host`) only configures Claude Code. Do not run it expecting Devin wiring.

### 5. Report

Always report what you ran and the outcome (`hc status` summary, or doctor failures). Do not claim the index is ready without evidence from status/doctor.
