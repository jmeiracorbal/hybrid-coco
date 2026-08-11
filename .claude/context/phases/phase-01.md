# Phase 01 — Index hygiene & CLI completeness

Status: **next**
Depends on: —
Roadmap: `.claude/context/plan.md`

## Intent

Make advertised indexing behavior match implementation, and keep the index directory out of version control by default.

## Scope

- Implement `--exclude` for `hc index` and `hc update` (pathspec / fnmatch relative to project root)
- `hc init` appends `.hybrid-coco/` to `.gitignore` when missing (idempotent)
- Optional: SessionStart path runs `hc update` when `.hybrid-coco/index.db` exists (no full reindex)
- Do not change MCP tool names or response shapes unless required for exclude messaging

## Non-goals

- Full settings YAML (phase 08)
- New languages (phase 04)

## Exit criteria

- [ ] Exclude patterns change which files are indexed (covered by tests)
- [ ] Fresh `hc init` leaves `.hybrid-coco/` ignored
- [ ] Existing hooks still receive usable hc CLI output
- [ ] README CLI section reflects real `--exclude` behavior

## Notes for implementers

Fail fast if an exclude pattern is empty or malformed — no silent ignore, no hardcoded fallbacks for missing params.
