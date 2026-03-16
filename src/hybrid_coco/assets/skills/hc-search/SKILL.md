---
name: hc-search
description: Search the hybrid-coco code index for symbols, functions, and definitions
user-invokable: true
args:
  - name: query
    description: What to search for (symbol name, concept, or keyword)
    required: true
---

Search the hybrid-coco index for: $ARGUMENTS

Use the `hc_search` MCP tool with the query above. If the tool is not available:
- Check that `hc serve` is running from the project root
- Or run `/hc-init` to set up hybrid-coco for this project

Present results grouped by file, showing: symbol kind, line number, signature, and docstring if available.
