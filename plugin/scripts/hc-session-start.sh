#!/usr/bin/env bash
# hybrid-coco SessionStart hook
# Incremental hc update when the cwd already has an index (never creates one).
# Does not write ~/.claude/CLAUDE.md — project pointers come from `hc init`.

if [ -f ".hybrid-coco/index.db" ] && command -v hc >/dev/null 2>&1; then
  hc update . >/dev/null 2>&1 || true
fi

exit 0
