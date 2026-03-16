#!/usr/bin/env bash
# hybrid-coco PreToolUse hook — advisory only
# Suggests hc_* tools when agent uses Read/Grep on indexed content

# Guards
command -v jq &>/dev/null || exit 0
command -v sqlite3 &>/dev/null || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)

case "$TOOL_NAME" in
  Read|Grep) ;;
  *) exit 0 ;;
esac

# Find index walking up from cwd (max 4 levels)
INDEX_DB=""
for dir in "." ".." "../.." "../../.."; do
  if [ -f "$dir/.hybrid-coco/index.db" ]; then
    INDEX_DB=$(cd "$dir" && pwd)/.hybrid-coco/index.db
    break
  fi
done
[ -n "$INDEX_DB" ] || exit 0

if [ "$TOOL_NAME" = "Read" ]; then
  FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
  [ -n "$FILE_PATH" ] || exit 0
  REL_PATH=$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1]))" "$FILE_PATH" 2>/dev/null) || exit 0
  IS_INDEXED=$(sqlite3 "$INDEX_DB" "SELECT 1 FROM files WHERE path='$REL_PATH' LIMIT 1" 2>/dev/null || echo "")
  if [ "$IS_INDEXED" = "1" ]; then
    echo "[hybrid-coco] '$REL_PATH' is indexed. Prefer: hc_file_context(\"$REL_PATH\")" >&2
  fi
fi

if [ "$TOOL_NAME" = "Grep" ]; then
  PATTERN=$(echo "$INPUT" | jq -r '.tool_input.pattern // empty' 2>/dev/null)
  [ -n "$PATTERN" ] || exit 0
  echo "[hybrid-coco] Index available. Prefer: hc_search(\"$PATTERN\")" >&2
fi

exit 0
