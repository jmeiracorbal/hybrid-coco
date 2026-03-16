---
name: hc-init
description: Initialize hybrid-coco in the current project — index code and register MCP server
user-invokable: true
---

Initialize hybrid-coco in the current project by running:

```bash
hc init .
```

This will:
1. Index all source files in the current directory
2. Register the MCP server in `.claude/settings.json`

After running, report:
- Number of files indexed and symbols found
- Location of the index (`.hybrid-coco/index.db`)
- That the user needs to restart Claude Code to load the MCP server

If `hc` is not installed, tell the user: `pip install hybrid-coco`
