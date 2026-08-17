# hybrid-coco — Local Code Intelligence

Self-contained local component: SQLite index, `hc` CLI, `hc_*` MCP tools, hooks, awareness, and skills — no external services required.

Index-based code navigation. Same context quality, fewer tokens.

## What's included

- `.hybrid-coco/index.db` in the project workspace
- `hc index` / `hc update` / `hc query` / `hc symbol` / `hc file-context` / `hc snippet` / `hc structure`
- MCP tools: `hc_search`, `hc_symbol`, `hc_file_context`, `hc_snippet`, `hc_structure`, `hc_status`
- Claude Code hooks and skills (`hybrid-coco`, `hc-init`, `hc-search`)
- Cursor MCP, skills, and hooks (`hc init --host cursor`)

## Decision tree

```
Need to understand a file?
  └─ hc_file_context("path")          ← always first
       ├─ answer found in signatures/structure? → DONE
       └─ need a specific function body?
            └─ hc_snippet("path", line_start, line_end)  ← bounded slice

Need to find something across the codebase?
  ├─ know the name? → hc_symbol("name")
  ├─ know a pattern? → hc_search("query")
  └─ know the shape? → hc_structure("function"|"method"|"class"|"import")
       └─ found lines? → hc_snippet("path", line_start, line_end)

Need to read a full file?
  └─ only if you need most of its content for the task
     (e.g. full refactor, line-by-line review)
```

## Tools

| Tool | Use when |
|---|---|
| `hc_file_context("path")` | Before any Read — get all symbols, signatures, line numbers |
| `hc_snippet("path", start, end)` | Read only the lines you need (1-based, inclusive) |
| `hc_structure("kind", path?, lang?, offset?, limit?)` | Find functions/methods/classes/imports by shape |
| `hc_search("query", path?, lang?, offset?, limit?)` | Before any Grep — FTS5 search; optional path/lang filters AND together |
| `hc_symbol("name", path?, lang?, offset?, limit?)` | Exact/prefix symbol lookup; same optional filters |
| `hc_status()` | Check what's indexed before exploring |

## The two-step snippet pattern

**Instead of reading an entire file to find one function:**

```
# Step 1 — navigate
hc_file_context("src/some_file.py")
→ "my_function @ line 47"

# Step 2 — read only what you need
hc_snippet("src/some_file.py", 47, 86)
```

**Rule**: after `hc_file_context` or `hc_symbol`, use `hc_snippet` with the symbol's line range. Avoid full-file Read unless the task needs most of the file.

## When full Read is justified

- Refactoring the entire file
- Line-by-line security or logic review
- The file is short (few lines)
- hc tools are unavailable (index not built)

## If MCP tools are unavailable

```bash
hc init        # index + register MCP server + skills/hooks (Claude Code)
hc init --host cursor
# then restart the agent host
```

Lifecycle skills (after `hc init`): `/hc-init` (setup/repair), `/hc-search` (query). Prefer `hc update` over full `hc index` when `.hybrid-coco/index.db` already exists.
