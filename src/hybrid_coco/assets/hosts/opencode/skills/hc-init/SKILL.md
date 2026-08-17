---
name: hc-init
description: Initialize or repair hybrid-coco for OpenCode — index if missing, register opencode.json MCP, plugin, and skills. Prefer over full reindex when an index already exists.
user-invokable: true
---

# hc-init (OpenCode)

Own the hybrid-coco lifecycle for this OpenCode project. Prefer the smallest action that restores a working index + MCP wiring.

## Rules (anti-storm)

- If `.hybrid-coco/index.db` **exists**, do **not** run `hc index` unless the user asked for a full rebuild or `hc doctor` / a failed query made that necessary after `hc reset`.
- The JS plugin `tool.execute.after` may already run `hc update`. Do not stack a full reindex on top.
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
hc init . --host opencode
```

Then report: files/symbols indexed, index path, that OpenCode may need a restart to load MCP from `opencode.json` and the plugin from `.opencode/plugins/hybrid-coco.js`.

If **present**: skip `hc init` unless MCP/plugin are clearly unregistered (see step 4).

### 3. Stale or empty?

```bash
hc status .
```

- Files/symbols look wrong after edits → `hc update .`
- Suspect corruption → `hc doctor .`
- User wants a wipe → `hc reset -f` (add `--all` only if they also want the project MCP entry removed), then `hc init . --host opencode`

### 4. MCP / plugin

If `hc_status` / `hc_*` tools are unavailable after an index exists:

```bash
hc init . --host opencode
```

Confirm `opencode.json` has `mcp.hybrid-coco` with `type: "local"` and `command: ["hc", "serve"]`, `.opencode/plugins/hybrid-coco.js` exists (OpenCode has no `hooks.json`), and skills exist under `.opencode/skills/`. Restart OpenCode if MCP or the plugin was newly registered.

Default `hc init` (no `--host`) only configures Claude Code. Do not run it expecting OpenCode wiring.

### 5. Report

Always report what you ran and the outcome (`hc status` summary, or doctor failures). Do not claim the index is ready without evidence from status/doctor.
