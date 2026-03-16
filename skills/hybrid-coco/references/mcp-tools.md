# hybrid-coco MCP Tools Reference

## Protocol

MCP over stdio (stdin/stdout JSON-RPC 2.0). Compatible with Claude Code without additional configuration.
Library: `mcp` from PyPI (official Anthropic Python SDK).

## Launch

```bash
hc serve          # run from project root (where .hybrid-coco/index.db exists)
```

If no index is found, exits immediately with: `No index found. Run: hc index .`

## Configuration in Claude Code

Written by `hc init` to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "hybrid-coco": {
      "command": "hc",
      "args": ["serve"],
      "type": "stdio"
    }
  }
}
```

The server is launched by Claude Code from the project root. Index path resolution depends on this cwd — correct for per-project isolation.

---

## Tools

### `hc_search`

**Input:** `query: str`, `limit?: int = 20`

FTS5 full-text search over name, signature, and docstring fields. Use for concept or keyword searches when you do not know the exact symbol name.

**Response example:**

```
[src/utils/jwt.rs:15] function validate_token
  sig: pub fn validate_token(token: &str) -> Result<Claims>
  doc: Validates and decodes a JWT bearer token

[src/auth/middleware.rs:42] function check_token
  sig: pub fn check_token(req: &Request) -> bool
  doc: Checks if request carries a valid bearer token
```

---

### `hc_symbol`

**Input:** `name: str`

Exact lookup by symbol name, with prefix fallback if no exact match is found. Use when you know the name of the function, class, or variable.

**Response example:**

```
function run @ src/git.rs:45-67
  sig: pub fn run(args: GitArgs) -> Result<()>
  doc: Executes git command with token-optimized output
```

---

### `hc_file_context`

**Input:** `path: str`

Returns all symbols in a file, grouped by kind (functions, classes, imports), with line numbers and signatures. Use this before reading a file to get structural context with minimal tokens.

**Response example:**

```
File: src/git.rs (rust) — 12 symbols

Functions (8):
  run @ 32        pub fn run(cmd: GitCommand, args: &[String]) -> Result<()>
  format_log @ 89  fn format_log(output: &str) -> String

Imports (4):
  use crate::tracking
  use crate::filter
```

---

### `hc_status`

**Input:** (none)

Returns index stats: files indexed, symbol counts by kind, last update timestamp, detected languages. Use to verify the index is current before starting work.

**Response example:**

```
Index: .hybrid-coco/index.db
Files:   47 indexed
Symbols: 312 (187 functions, 23 classes, 102 imports)
Updated: 2026-03-12 15:42
Languages: python, rust, typescript
```

---

## Notes

- All responses are plain structured text, not raw JSON. Each response is self-describing and compact.
- Tools are designed to return minimal, compact output to keep token usage low.
- Use the `limit` parameter on `hc_search` to reduce response size when needed.
