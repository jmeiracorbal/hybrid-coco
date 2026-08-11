# Phase 05 — Agent skill owns lifecycle

Status: pending
Depends on: phase 01 (SessionStart update behavior)
Roadmap: `.claude/context/plan.md`

## Intent

The agent initializes, updates, and queries the index without asking the user to run setup commands first.

## Scope

- Rewrite / align `skills/hybrid-coco/SKILL.md` and packaged asset skills
- Ownership rules: missing index → init/index; after code edits → update; then `hc_*`
- Coordinate with SessionStart so we do not thrash full reindexes
- Preserve `hc_*` tool naming and Claude Code as primary host

## Exit criteria

- [ ] Skill is end-to-end actionable from a clean clone
- [ ] No contradictory instructions vs hooks/awareness
- [ ] Plugin and repo skills stay in sync (or one is clearly canonical)

## Notes for implementers

Skill text is operational, not marketing. Prefer concrete commands and failure branches.
