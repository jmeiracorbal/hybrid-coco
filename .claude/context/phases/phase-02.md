# Phase 02 — Query filters

Status: pending
Depends on: phase 01 (preferred, not hard)
Roadmap: `.claude/context/plan.md`

## Intent

Let agents narrow FTS and symbol lookups by path and language, with pagination.

## Scope

- `hc query`: `--path`, `--lang` (repeatable), `--offset`, `--limit`
- MCP `hc_search`: same parameters in the tool schema
- `hc_symbol` / CLI `symbol`: path/lang filters where applicable
- Update skill + awareness docs for filter usage

## Exit criteria

- [ ] Filters compose correctly (AND semantics documented)
- [ ] MCP schema lists new fields
- [ ] Tests for path, lang, offset/limit, and empty-result cases

## Notes for implementers

Required parameters stay required. Optional filter flags may be omitted by the caller; do not invent default path/lang values beyond “no filter”.
