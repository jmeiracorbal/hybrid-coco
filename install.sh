#!/usr/bin/env bash
# hybrid-coco installer
# Usage: curl -fsSL https://raw.githubusercontent.com/jmeiracorbal/hybrid-coco/main/install.sh | bash
set -euo pipefail

PACKAGE="hybrid-coco"
HOOKS_DIR="${HOME}/.claude/hooks"
CLAUDE_DIR="${HOME}/.claude"
SETTINGS="${CLAUDE_DIR}/settings.json"
AWARENESS="${CLAUDE_DIR}/hybrid-coco.md"
CLAUDE_MD="${CLAUDE_DIR}/CLAUDE.md"

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[hybrid-coco]${NC} $*"; }
warn()  { echo -e "${YELLOW}[hybrid-coco]${NC} $*"; }
error() { echo -e "${RED}[hybrid-coco]${NC} $*" >&2; }

# ── 1. Python 3.11+ ───────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null; then
    ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor:02d}')" 2>/dev/null || echo "0")
    if [ "$ver" -ge 311 ] 2>/dev/null; then
      PYTHON="$cmd"
      break
    fi
  fi
done
if [ -z "$PYTHON" ]; then
  error "Python 3.11+ is required. Please install it and try again."
  exit 1
fi
info "Using $($PYTHON --version)"

# ── 2. Install hc ─────────────────────────────────────────────────────────────
if command -v hc &>/dev/null; then
  info "hc already installed — upgrading"
  UPGRADE=1
else
  UPGRADE=0
fi

if command -v uv &>/dev/null; then
  info "Installing via uv..."
  uv tool install --upgrade "$PACKAGE" 2>/dev/null || uv tool install "$PACKAGE"
elif command -v pipx &>/dev/null; then
  info "Installing via pipx..."
  if [ "$UPGRADE" -eq 1 ]; then
    pipx upgrade "$PACKAGE" 2>/dev/null || pipx install "$PACKAGE"
  else
    pipx install "$PACKAGE"
  fi
else
  info "Installing via pip (no uv or pipx found)..."
  "$PYTHON" -m pip install --user --upgrade "$PACKAGE"
fi

# Verify
if ! command -v hc &>/dev/null; then
  warn "hc not found in PATH after install."
  warn "You may need to add ~/.local/bin to your PATH:"
  warn "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc"
fi

# ── 3. Hook scripts ───────────────────────────────────────────────────────────
mkdir -p "$HOOKS_DIR"

info "Installing hook scripts..."

cat > "$HOOKS_DIR/hc-pre-tool-use.sh" << 'HOOK'
#!/usr/bin/env bash
# hybrid-coco PreToolUse hook — advisory only
# Suggests hc_* tools when agent uses Read/Grep on indexed content

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
HOOK

cat > "$HOOKS_DIR/hc-post-tool-use.sh" << 'HOOK'
#!/usr/bin/env bash
# hybrid-coco PostToolUse hook — keeps index fresh after file writes

command -v jq &>/dev/null || exit 0
command -v hc &>/dev/null || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)

case "$TOOL_NAME" in
  Write|Edit) ;;
  *) exit 0 ;;
esac

# Find project root with hybrid-coco index
for dir in "." ".." "../.." "../../.."; do
  if [ -f "$dir/.hybrid-coco/index.db" ]; then
    PROJECT_ROOT=$(cd "$dir" && pwd)
    hc update "$PROJECT_ROOT" 2>/dev/null || true
    exit 0
  fi
done

exit 0
HOOK

chmod +x "$HOOKS_DIR/hc-pre-tool-use.sh"
chmod +x "$HOOKS_DIR/hc-post-tool-use.sh"

# ── 4. Awareness file ─────────────────────────────────────────────────────────
info "Installing awareness file..."

cat > "$AWARENESS" << 'AWARENESS_EOF'
# hybrid-coco — Local Code Intelligence

Index-based code navigation. Same context quality, fewer tokens.

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
| `hc_search("query")` | Before any Grep — FTS5 search over names, signatures, docstrings |
| `hc_symbol("name")` | Exact/prefix symbol lookup — get file + line immediately |
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
hc init        # index + register MCP server
# then restart Claude Code
```
AWARENESS_EOF

# ── 5. Patch ~/.claude/settings.json ─────────────────────────────────────────
info "Patching Claude Code settings..."

"$PYTHON" - << PYEOF
import json, os, sys

settings_path = os.path.expanduser("${SETTINGS}")
hooks_dir = os.path.expanduser("${HOOKS_DIR}")

# Load or create settings
if os.path.exists(settings_path):
    with open(settings_path) as f:
        try:
            cfg = json.load(f)
        except json.JSONDecodeError:
            print("[hybrid-coco] Warning: settings.json is invalid JSON — skipping hook patch", file=sys.stderr)
            sys.exit(0)
else:
    cfg = {}

cfg.setdefault("hooks", {})
cfg["hooks"].setdefault("PreToolUse", [])
cfg["hooks"].setdefault("PostToolUse", [])

def hook_exists(entries, matcher, script):
    for entry in entries:
        if entry.get("matcher") == matcher:
            for h in entry.get("hooks", []):
                if script in h.get("command", ""):
                    return True
    return False

def add_hook(entries, matcher, script):
    if hook_exists(entries, matcher, script):
        return False
    # Try to append to existing matcher entry
    for entry in entries:
        if entry.get("matcher") == matcher:
            entry["hooks"].append({"type": "command", "command": script})
            return True
    # Create new matcher entry
    entries.append({"matcher": matcher, "hooks": [{"type": "command", "command": script}]})
    return True

pre_script  = os.path.join(hooks_dir, "hc-pre-tool-use.sh")
post_script = os.path.join(hooks_dir, "hc-post-tool-use.sh")

changed = False
changed |= add_hook(cfg["hooks"]["PreToolUse"],  "Read|Grep",   pre_script)
changed |= add_hook(cfg["hooks"]["PostToolUse"], "Write|Edit",  post_script)

if changed:
    with open(settings_path, "w") as f:
        json.dump(cfg, f, indent=2)
    print("[hybrid-coco] settings.json updated")
else:
    print("[hybrid-coco] settings.json already configured — no changes needed")
PYEOF

# ── 6. Add @hybrid-coco.md to CLAUDE.md ──────────────────────────────────────
if [ -f "$CLAUDE_MD" ]; then
  if grep -q "@hybrid-coco.md" "$CLAUDE_MD"; then
    info "CLAUDE.md already references @hybrid-coco.md"
  else
    info "Adding @hybrid-coco.md to CLAUDE.md..."
    echo "" >> "$CLAUDE_MD"
    echo "@hybrid-coco.md" >> "$CLAUDE_MD"
  fi
else
  info "Creating CLAUDE.md with @hybrid-coco.md reference..."
  echo "@hybrid-coco.md" > "$CLAUDE_MD"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
info "Installation complete!"
echo ""
echo "  Next steps:"
echo "  1. Restart Claude Code (or reload the window)"
echo "  2. In any project: hc init"
echo "  3. Claude will now prefer hc_* tools over Read/Grep"
echo ""
echo "  To verify: hc --version"
echo ""
