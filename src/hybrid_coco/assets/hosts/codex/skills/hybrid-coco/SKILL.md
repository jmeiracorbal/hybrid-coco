---
name: hybrid-coco
description: Local code intelligence for Codex — prefer hc_* MCP tools over Bash cat/head/rg/grep.
---

# hybrid-coco (Codex)

Local SQLite index. Prefer `hc_*` MCP tools over Bash `cat` / `head` / `rg` / `grep`.

**Host:** OpenAI Codex. MCP: `.codex/config.toml` (`[mcp_servers.hybrid-coco]`). Skills: `.agents/skills/` and `~/.agents/skills/`.

Codex has no Read/Grep tools. Indexed-file lookup goes through Bash; edits go through `apply_patch`.

**Hooks this host actually has:**

| Event | When | hybrid-coco |
|---|---|---|
| `PreToolUse` matcher `Bash` | before a shell command | block `cat`/`head`/`rg`/`grep` on indexed files; `decision: block` + `hc_*` output |
| `PostToolUse` matcher `apply_patch\|Edit\|Write` | after edits | `hc update` |
| `SessionStart` | session begins | incremental `hc update` if the index exists |

Do not invent a Read/Grep matcher — Codex will not fire it.

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

| Situation | Tool | Instead of (Codex) |
|---|---|---|
| Find by exact/prefix name | `hc_symbol` | Bash `rg` / `grep` |
| Search by concept/keyword | `hc_search` | Bash `rg` / `grep` |
| Search by code shape | `hc_structure` | Bash `rg` / `grep` |
| Understand a file | `hc_file_context` | Bash `cat` / `head` |
| Read a known line range | `hc_snippet` | Bash `sed` / `head` |
| Check coverage / health | `hc_status` | `ls` / `find` |

Optional filters on `hc_symbol` / `hc_search`: `path` (gitignore-style), `lang` (e.g. `["python"]`), `offset` / `limit`. Filters AND together.

## Lifecycle (do not fight hooks)

`SessionStart` and `PostToolUse` already run incremental `hc update` when an index exists.

- **No** `.hybrid-coco/index.db` → use `/hc-init` (or `hc init . --host codex`). Do not invent a full reindex loop.
- Index exists but results look stale → `hc update .` only.
- Full `hc index` only when the index is missing or the user explicitly wants a full rebuild after `hc doctor` / `hc reset`.

## Two-step snippet

After `hc_file_context` or `hc_symbol`, call `hc_snippet(path, line_start, line_end)` with the symbol's line range (1-based, inclusive). Full-file `cat` only for whole-file refactors, line-by-line review, or very short files.

## Troubleshooting (short)

- **`hc_*` unavailable** → `/hc-init`, then restart Codex if `.codex/config.toml` was just written.
- **Symbol missing** → language may be unsupported; fall back to Bash `rg` on unindexed files. Or run `hc doctor` / `/hc-init` if the index is empty.
- **Snippet out of range** → re-check lines from `hc_symbol` / `hc_file_context`; paths are relative to project root.
- **Output is incomplete or unclear** → narrow the query with `path`, `lang`, or `limit`, then retry.

## References

- `references/cli-commands.md`
- `references/mcp-tools.md`
