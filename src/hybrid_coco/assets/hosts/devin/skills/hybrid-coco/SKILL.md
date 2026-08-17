---
name: hybrid-coco
description: Local code intelligence for Devin — prefer hc_* MCP tools over native read/grep.
---

# hybrid-coco (Devin)

Local SQLite index. Prefer `hc_*` MCP tools over Devin `read` / `grep`.

**Host:** Devin. MCP: `.devin/mcp_config.json`. Skills: `.devin/skills/` and `~/.config/devin/skills/`.

Tool names are **lowercase**. The read payload uses `file_path`.

**Hooks this host actually has** (`.devin/hooks.v1.json` is the hooks object — no wrapper `hooks` key):

| Event | Matcher | hybrid-coco |
|---|---|---|
| `PreToolUse` | `^(read\|grep)$` | `decision: block` + `hc_*` output |
| `PostToolUse` | `^(write\|edit)$` | `hc update` |
| `SessionStart` | (none) | incremental `hc update` if the index exists |

Block payload is Claude-compatible `{decision: "block", reason}`. Matchers are regex, as Devin documents.

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

| Situation | Tool | Instead of (Devin) |
|---|---|---|
| Find by exact/prefix name | `hc_symbol` | `grep` |
| Search by concept/keyword | `hc_search` | `grep` |
| Search by code shape | `hc_structure` | `grep` / `read` |
| Understand a file | `hc_file_context` | `read` (`file_path`) |
| Read a known line range | `hc_snippet` | `read` with offset |
| Check coverage / health | `hc_status` | glob / ls |

Optional filters on `hc_symbol` / `hc_search`: `path` (gitignore-style), `lang` (e.g. `["python"]`), `offset` / `limit`. Filters AND together.

## Lifecycle (do not fight hooks)

`SessionStart` and `PostToolUse` already run incremental `hc update` when an index exists.

- **No** `.hybrid-coco/index.db` → use `/hc-init` (or `hc init . --host devin`). Do not invent a full reindex loop.
- Index exists but results look stale → `hc update .` only.
- Full `hc index` only when the index is missing or the user explicitly wants a full rebuild after `hc doctor` / `hc reset`.

## Two-step snippet

After `hc_file_context` or `hc_symbol`, call `hc_snippet(path, line_start, line_end)` with the symbol's line range (1-based, inclusive). Full-file `read` only for whole-file refactors, line-by-line review, or very short files.

## Troubleshooting (short)

- **`hc_*` unavailable** → `/hc-init`, then restart Devin if `.devin/mcp_config.json` was just written.
- **Symbol missing** → language may be unsupported; fall back to `grep`. Or run `hc doctor` / `/hc-init` if the index is empty.
- **Snippet out of range** → re-check lines from `hc_symbol` / `hc_file_context`; paths are relative to project root.
- **Output is incomplete or unclear** → narrow the query with `path`, `lang`, or `limit`, then retry.

## References

- `references/cli-commands.md`
- `references/mcp-tools.md`
