---
name: hybrid-coco
description: Local code intelligence for Cursor — prefer hc_* MCP tools over Read/Grep.
---

# hybrid-coco (Cursor)

Local SQLite index. Prefer `hc_*` MCP tools over Cursor `Read` / `Grep`.

**Host:** Cursor. MCP: `.cursor/mcp.json`. Skills: `.cursor/skills/` and `~/.cursor/skills/`.

**Hooks this host actually has** (narrower than Claude Code):

| Event | When | hybrid-coco |
|---|---|---|
| `preToolUse` matcher `Read\|Grep` | before Read/Grep | deny + `agent_message` with `hc_*` output |
| `beforeReadFile` | before a file is sent to the model | deny indexed files; use `hc_file_context` |
| `postToolUse` matcher `Write\|StrReplace` | after edits | `hc update` |
| `afterFileEdit` | after a file write | `hc update` |
| `sessionStart` | session begins | incremental `hc update` if the index exists |

Cloud agents only load **project** `.cursor/hooks.json`. Do not rely on `~/.cursor/hooks.json` in cloud.

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
            └─ hc_snippet("path", line_start, line_end)

Need to find something across the codebase?
  ├─ know the name? → hc_symbol("name")
  ├─ know a pattern? → hc_search("query")
  └─ know the shape (fn/class/import)? → hc_structure("function"|"method"|"class"|"import")
       └─ found lines? → hc_snippet("path", line_start, line_end)

Need to read a full file?
  └─ only if you need most of its content for the task
```

## Tool map

| Situation | Tool | Instead of (Cursor) |
|---|---|---|
| Find by exact/prefix name | `hc_symbol` | Read + Grep |
| Search by concept/keyword | `hc_search` | Grep |
| Search by code shape | `hc_structure` | Grep/Read |
| Understand a file | `hc_file_context` | Read |
| Read a known line range | `hc_snippet` | Read with offset/limit |
| Check coverage / health | `hc_status` | glob / ls |

Optional filters on `hc_symbol` / `hc_search`: `path` (gitignore-style), `lang` (e.g. `["python"]`), `offset` / `limit`. Filters AND together.

## Lifecycle (do not fight hooks)

`sessionStart` and `afterFileEdit` / `postToolUse` already run incremental `hc update` when an index exists.

- **No** `.hybrid-coco/index.db` → use `/hc-init` (or `hc init . --host cursor`). Do not invent a full reindex loop.
- Index exists but results look stale → `hc update .` only.
- Full `hc index` only when the index is missing or the user explicitly wants a full rebuild after `hc doctor` / `hc reset`.

## Two-step snippet

After `hc_file_context` or `hc_symbol`, call `hc_snippet(path, line_start, line_end)` with the symbol's line range (1-based, inclusive). Full-file Read only for whole-file refactors, line-by-line review, or very short files.

## Troubleshooting (short)

- **`hc_*` unavailable** → `/hc-init`, then restart Cursor if `.cursor/mcp.json` was just written.
- **Symbol missing** → language may be unsupported; fall back to Grep. Or run `hc doctor` / `/hc-init` if the index is empty.
- **Snippet out of range** → re-check lines from `hc_symbol` / `hc_file_context`; paths are relative to project root.
- **Output is incomplete or unclear** → narrow the query with `path`, `lang`, or `limit`, then retry.

## References

- `references/cli-commands.md`
- `references/mcp-tools.md`
