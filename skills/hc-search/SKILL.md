---
name: hc-search
description: Query the hybrid-coco index — choose hc_symbol, hc_search, or hc_file_context; apply path/lang filters. Does not reindex.
user-invokable: true
args:
  - name: query
    description: Symbol name, concept, keyword, or file path to inspect
    required: true
---

# hc-search

Search or navigate the hybrid-coco index for: $ARGUMENTS

This skill **queries** only. It does not run `hc init` / `hc index` unless tools are unavailable (then hand off to `/hc-init`).

## Choose the tool

| Intent | Call |
|---|---|
| Exact or prefix symbol name | `hc_symbol(name=...)` |
| Concept / keyword / docstring text | `hc_search(query=...)` |
| What is in one file | `hc_file_context(path=...)` |
| Is anything indexed? | `hc_status()` |

## Filters and pagination

On `hc_symbol` and `hc_search` (optional, AND together):

- `path` — gitignore-style pattern over indexed paths
- `lang` — e.g. `["python"]`, `["rust"]`
- `offset` / `limit` — page or shrink results (`limit` default 20 for search)

Omit a filter for no restriction.

## If MCP tools are missing

1. Call `hc_status` if present; otherwise check for `.hybrid-coco/index.db`
2. Hand off to `/hc-init` — do not full-reindex from this skill as a first step

## Present results

Group by file when useful. For each hit show: kind, path, line range, signature, docstring if any.

After a hit, if the body is needed: `Read(path, offset=line_start, limit=…)` — not the whole file.

## CLI fallback (same project root)

```bash
hc symbol <NAME> [--path PAT] [--lang LANG]...
hc query <TEXT>  [--path PAT] [--lang LANG]...
hc file-context <PATH>
hc status
```
