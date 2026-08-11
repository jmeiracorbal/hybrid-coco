#!/usr/bin/env bash
# hybrid-coco SessionStart hook
# Ensures ~/.claude/hybrid-coco.md exists so Claude knows to use hc_* tools.
# If a project index already exists in cwd, runs incremental hc update.

CLAUDE_DIR="${HOME}/.claude"
AWARENESS="${CLAUDE_DIR}/hybrid-coco.md"
CLAUDE_MD="${CLAUDE_DIR}/CLAUDE.md"
PLUGIN_AWARENESS="${CLAUDE_PLUGIN_ROOT}/awareness/hybrid-coco.md"

# Write awareness file if missing
if [ ! -f "$AWARENESS" ]; then
  mkdir -p "$CLAUDE_DIR"
  cp "$PLUGIN_AWARENESS" "$AWARENESS"
fi

# Add @hybrid-coco.md to CLAUDE.md if not already referenced
if ! grep -q "@hybrid-coco.md" "$CLAUDE_MD" 2>/dev/null; then
  [ -f "$CLAUDE_MD" ] && echo "" >> "$CLAUDE_MD"
  echo "@hybrid-coco.md" >> "$CLAUDE_MD"
fi

# Incremental refresh when the cwd already has an index (never creates one)
if [ -f ".hybrid-coco/index.db" ] && command -v hc >/dev/null 2>&1; then
  hc update . >/dev/null 2>&1 || true
fi

exit 0
