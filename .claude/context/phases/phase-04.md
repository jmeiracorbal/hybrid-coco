# Phase 04 — Language coverage

Status: pending
Depends on: —
Roadmap: `.claude/context/plan.md`

## Intent

Expand tree-sitter symbol extraction beyond Python / JS / TS / Rust.

## Priority

1. Go
2. Java
3. C / C++ (including common header extensions)

## Per language

- Add tree-sitter grammar dependency in `pyproject.toml`
- Parser module under `src/hybrid_coco/parsers/`
- Register extensions in `detect_language` / `get_parser`
- Fixtures + tests for functions, types/classes, methods, imports (as grammar allows)
- README language table

## Exit criteria

- [ ] Each prioritized language indexes real fixtures with non-zero symbols
- [ ] Unsupported files still skip cleanly (no crash)
- [ ] Package still installs with `pip install hybrid-coco` (deps stay reasonable)

## Notes for implementers

Do not stub parsers that return empty success for every file — unsupported constructs may yield fewer symbols, but the happy path must extract the main kinds.
