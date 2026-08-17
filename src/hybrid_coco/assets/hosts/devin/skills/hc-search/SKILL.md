---
name: hc-search
description: Query the hybrid-coco index from Devin — choose hc_symbol, hc_search, or hc_file_context. Does not reindex.
user-invokable: true
args:
  - name: query
    description: Symbol name, concept, keyword, or file path to inspect
    required: true
---

# hc-search (Devin)

Search or navigate the hybrid-coco index for: $ARGUMENTS

This skill **queries** only. It does not run `hc init` / `hc index` unless tools are unavailable (then hand off to `/hc-init`).

Do not open files with Devin `read` or `grep` to answer this query. Tool names are lowercase; `read` uses `file_path`. Use `hc_*` first.

## Choose the tool

| Intent | Call |
|---|---|
| Exact or prefix symbol name | `hc_symbol(name=...)` |
| Concept / keyword / docstring text | `hc_search(query=...)` |
| Code shape (function/method/class/import) | `hc_structure(kind=...)` |
| What is in one file | `hc_file_context(path=...)` |
| Read a known line range | `hc_snippet(path=..., line_start=..., line_end=...)` |
| Is anything indexed? | `hc_status()` |

## Filters and pagination

On `hc_symbol` and `hc_search` (optional, AND together):

- `path` — gitignore-style pattern over indexed paths
- `lang` — e.g. `["python"]`, `["rust"]`
- `offset` / `limit` — page or shrink results (`limit` default 20 for search)

Omit a filter for no restriction.

## If MCP tools are missing

1. Call `hc_status` if present; otherwise check for `.hybrid-coco/index.db`
2. Hand off to `/hc-init` (`hc init . --host devin`) — do not full-reindex from this skill as a first step

## Present results

Group by file when useful. For each hit show: kind, path, line range, signature, docstring if any.

After a hit, if the body is needed: `hc_snippet(path, line_start, line_end)` from the symbol range — not Devin `read` of the whole file.

## CLI fallback (same project root)

```bash
hc symbol <NAME> [--path PAT] [--lang LANG]...
hc query <TEXT>  [--path PAT] [--lang LANG]...
hc file-context <PATH>
hc snippet <PATH> <START> <END>
hc status
```
