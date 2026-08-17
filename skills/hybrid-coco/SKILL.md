---
name: hybrid-coco
description: Self-contained local code intelligence — when and how to use hc_* tools for deterministic code navigation.
---

# hybrid-coco

Local SQLite index of the codebase. Prefer `hc_*` MCP tools over blind Read/Grep.

**Self-contained:** index, CLI, MCP tools, hooks, and skills ship together — no external services.

**Core principle:** Index once, query always.

**Supported languages:** Python, JavaScript/TypeScript, Rust, Go, Java, C, C++, C#, Kotlin, Swift.

## Related skills

| Need | Skill |
|---|---|
| Missing index, first setup, or broken wiring | `/hc-init` |
| Search / symbol lookup / file structure query | `/hc-search` |

## Decision tree

```
Need to understand a file?
  └─ hc_file_context("path")          ← always first
       ├─ answer found in signatures/structure? → DONE
       └─ need a specific function body?
            └─ Read("path", offset=N, limit=M)  ← targeted, not full file

Need to find something across the codebase?
  ├─ know the name? → hc_symbol("name")
  └─ know a pattern? → hc_search("query")
       └─ found it? → Read("path", offset=N, limit=M)  ← only that section

Need to read a full file?
  └─ only if you need most of its content for the task
```

## Tool map

| Situation | Tool | Instead of |
|---|---|---|
| Find by exact/prefix name | `hc_symbol` | Read + grep |
| Search by concept/keyword | `hc_search` | Recursive grep |
| Understand a file | `hc_file_context` | Full-file Read |
| Check coverage / health | `hc_status` | ls / find |

Optional filters on `hc_symbol` / `hc_search`: `path` (gitignore-style), `lang` (e.g. `["python"]`), `offset` / `limit`. Filters AND together.

## Lifecycle (do not fight hooks)

SessionStart and PostToolUse already run incremental `hc update` when an index exists.

- **No** `.hybrid-coco/index.db` → use `/hc-init` (or `hc init .`). Do not invent a full reindex loop.
- Index exists but results look stale → `hc update .` only. Never run `hc index` just because SessionStart already refreshed.
- Full `hc index` only when the index is missing or the user explicitly wants a full rebuild after `hc doctor` / `hc reset`.

## Two-step Read

After `hc_file_context` (or a symbol hit), Read only the needed range with `offset` + `limit`. Full-file Read only for whole-file refactors, line-by-line review, or very short files.

## Troubleshooting (short)

- **`hc_*` unavailable** → `/hc-init`, then restart Claude Code if MCP was just registered.
- **Symbol missing** → language may be unsupported; fall back to Grep. Or run `hc doctor` / `/hc-init` if the index is empty.
- **Output is incomplete or unclear** → narrow the query with `path`, `lang`, or `limit`, then retry.

## References

- `references/cli-commands.md`
- `references/mcp-tools.md`
