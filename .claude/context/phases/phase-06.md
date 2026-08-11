# Phase 06 — Symbol body / targeted snippet

Status: pending
Depends on: phase 02 (useful after filtered lookups)
Roadmap: `.claude/context/plan.md`

## Intent

Return a bounded code slice once the agent knows path + line range, instead of a full-file Read.

## Preferred design

Query-time disk read: `hc_snippet(path, line_start, line_end)` (CLI + MCP). Do **not** store full file bodies in SQLite by default.

## Scope

- Validate path is under the indexed project root
- Enforce max span (explicit limit; fail if exceeded — no silent truncation unless documented as a hard error alternative)
- Awareness / skill: prefer snippet when lines are known
- Optional: convenience on `hc_symbol` to include body for the matched symbol

## Exit criteria

- [ ] MCP + CLI return the requested line range
- [ ] Out-of-range / missing file fail explicitly
- [ ] Docs updated; hooks do not regress

## Notes for implementers

No fallback to “whole file” when the range is invalid — exit with an error.
