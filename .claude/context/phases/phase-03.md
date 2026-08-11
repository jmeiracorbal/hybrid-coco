# Phase 03 — Doctor, reset, version alignment

Status: pending
Depends on: —
Roadmap: `.claude/context/plan.md`

## Intent

Give humans and agents a health check, a clean wipe, and one consistent version string.

## Scope

- `hc doctor` — index file, schema, basic query smoke, language list, MCP/hooks registration hints, gtk-ai `hc_` passthrough reminder
- `hc reset` — remove index DB; optional broader cleanup; `-f` skips confirmation
- Version single source: `pyproject.toml` → CLI `--version` → plugin marketplace/plugin.json

## Exit criteria

- [ ] Doctor non-zero on missing/corrupt index
- [ ] Reset leaves a state where `hc index` works again
- [ ] All user-visible versions match the package version

## Notes for implementers

No silent “repair” that invents config. Doctor reports; reset deletes only what the user asked to reset.
