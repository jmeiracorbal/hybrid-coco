#!/usr/bin/env bash
# hybrid-coco PreToolUse hook — blocking
# Intercepts Read/Grep on indexed content and returns hc data directly.
# Blocks the tool so Claude uses hc output instead of reading the full file.

command -v jq      &>/dev/null || exit 0
command -v hc      &>/dev/null || exit 0
command -v sqlite3 &>/dev/null || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)

case "$TOOL_NAME" in
  Read|Grep) ;;
  *) exit 0 ;;
esac

# Find project root with hybrid-coco index (walk up max 4 levels)
PROJECT_ROOT=""
for dir in "." ".." "../.." "../../.."; do
  if [ -f "$dir/.hybrid-coco/index.db" ]; then
    PROJECT_ROOT=$(cd "$dir" && pwd)
    break
  fi
done
[ -n "$PROJECT_ROOT" ] || exit 0

INDEX_DB="$PROJECT_ROOT/.hybrid-coco/index.db"

if [ "$TOOL_NAME" = "Read" ]; then
  FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
  [ -n "$FILE_PATH" ] || exit 0

  REL_PATH=$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1]))" "$FILE_PATH" 2>/dev/null) || exit 0

  IS_INDEXED=$(sqlite3 "$INDEX_DB" "SELECT 1 FROM files WHERE path='$REL_PATH' LIMIT 1" 2>/dev/null)
  [ "$IS_INDEXED" = "1" ] || exit 0

  OFFSET=$(echo "$INPUT" | jq -r '.tool_input.offset // empty' 2>/dev/null)
  LIMIT=$(echo "$INPUT" | jq -r '.tool_input.limit // empty' 2>/dev/null)

  if [ -n "$OFFSET" ] && [ -n "$LIMIT" ] && [ "$OFFSET" != "null" ] && [ "$LIMIT" != "null" ]; then
    LINE_END=$((OFFSET + LIMIT - 1))
    HC_OUTPUT=$(cd "$PROJECT_ROOT" && hc snippet "$REL_PATH" "$OFFSET" "$LINE_END" 2>/dev/null) || exit 0
    [ -n "$HC_OUTPUT" ] || exit 0

    REASON=$(printf '[hybrid-coco] Snippet for %s:\n\n%s\n\nUse hc_snippet when line ranges are known.' \
      "$REL_PATH" "$HC_OUTPUT" | jq -Rs .)
    printf '{"decision":"block","reason":%s}\n' "$REASON"
    exit 0
  fi

  HC_OUTPUT=$(cd "$PROJECT_ROOT" && hc file-context "$REL_PATH" 2>/dev/null) || exit 0
  [ -n "$HC_OUTPUT" ] || exit 0

  REASON=$(printf '[hybrid-coco] Symbols for %s:\n\n%s\n\nUse hc_file_context first, then hc_snippet for the body.' \
    "$REL_PATH" "$HC_OUTPUT" | jq -Rs .)
  printf '{"decision":"block","reason":%s}\n' "$REASON"
  exit 0
fi

if [ "$TOOL_NAME" = "Grep" ]; then
  PATTERN=$(echo "$INPUT" | jq -r '.tool_input.pattern // empty' 2>/dev/null)
  [ -n "$PATTERN" ] || exit 0

  # Only intercept simple patterns — skip if pattern contains regex metacharacters
  if printf '%s' "$PATTERN" | grep -qE '[.^$*+?{}\[\]\\|()]'; then
    exit 0
  fi

  HC_OUTPUT=$(cd "$PROJECT_ROOT" && hc query "$PATTERN" 2>/dev/null) || exit 0
  [ -n "$HC_OUTPUT" ] || exit 0

  REASON=$(printf '[hybrid-coco] Search results for "%s":\n\n%s\n\nUse hc_search, then hc_snippet for matched ranges.' \
    "$PATTERN" "$HC_OUTPUT" | jq -Rs .)
  printf '{"decision":"block","reason":%s}\n' "$REASON"
  exit 0
fi

exit 0
