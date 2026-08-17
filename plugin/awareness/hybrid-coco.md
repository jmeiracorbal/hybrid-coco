# hybrid-coco — Local Code Intelligence

Self-contained local component: SQLite index, `hc` CLI, `hc_*` MCP tools, hooks, awareness, and skills — no external services required.

Index-based code navigation. Same context quality, fewer tokens.

## What's included

- `.hybrid-coco/index.db` in the project workspace
- `hc index` / `hc update` / `hc query` / `hc symbol` / `hc file-context`
- MCP tools: `hc_search`, `hc_symbol`, `hc_file_context`, `hc_status`
- Claude Code hooks and skills (`hybrid-coco`, `hc-init`, `hc-search`)

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
     (e.g. full refactor, line-by-line review)
```

## Tools

| Tool | Use when |
|---|---|
| `hc_file_context("path")` | Before any Read — get all symbols, signatures, line numbers |
| `hc_search("query", path?, lang?, offset?, limit?)` | Before any Grep — FTS5 search; optional path/lang filters AND together |
| `hc_symbol("name", path?, lang?, offset?, limit?)` | Exact/prefix symbol lookup; same optional filters |
| `hc_status()` | Check what's indexed before exploring |

## The two-step Read pattern

**Instead of reading an entire file to find one function:**

```
# Step 1 — navigate
hc_file_context("src/some_file.py")
→ "my_function @ line 47"

# Step 2 — read only what you need
Read("src/some_file.py", offset=47, limit=40)
```

**Rule**: after `hc_file_context`, use `Read` with `offset` + `limit` to read only the specific symbol you need. Never read from line 1 unless the task requires the whole file.

## When full Read is justified

- Refactoring the entire file
- Line-by-line security or logic review
- The file is short (few lines)
- hc tools are unavailable (index not built)

## If MCP tools are unavailable

```bash
hc init        # index + register MCP server + skills/hooks
# then restart Claude Code
```

Lifecycle skills (after `hc init`): `/hc-init` (setup/repair), `/hc-search` (query). Prefer `hc update` over full `hc index` when `.hybrid-coco/index.db` already exists.
