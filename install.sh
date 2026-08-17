#!/usr/bin/env bash
# hybrid-coco installer
# Usage: curl -fsSL https://raw.githubusercontent.com/jmeiracorbal/hybrid-coco/main/install.sh | bash
set -euo pipefail

PACKAGE="hybrid-coco"
HOOKS_DIR="${HOME}/.claude/hooks"
CLAUDE_DIR="${HOME}/.claude"
SETTINGS="${CLAUDE_DIR}/settings.json"

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
# Source of truth: src/hybrid_coco/assets/hooks/ (bundled with the package).
# Copied from there — never written inline here.
mkdir -p "$HOOKS_DIR"

info "Installing hook scripts from package assets..."

ASSETS_HOOKS=$("$PYTHON" -c "
import hybrid_coco, os
print(os.path.join(os.path.dirname(hybrid_coco.__file__), 'assets', 'hooks'))
" 2>/dev/null)

if [ -d "$ASSETS_HOOKS" ]; then
  cp "$ASSETS_HOOKS/hc-pre-tool-use.sh"  "$HOOKS_DIR/hc-pre-tool-use.sh"
  cp "$ASSETS_HOOKS/hc-post-tool-use.sh" "$HOOKS_DIR/hc-post-tool-use.sh"
  chmod +x "$HOOKS_DIR/hc-pre-tool-use.sh" "$HOOKS_DIR/hc-post-tool-use.sh"
else
  warn "Package assets not found — hook scripts not installed"
  warn "Try: pip install --upgrade hybrid-coco"
fi

# ── 4. Install agent skills ───────────────────────────────────────────────────
info "Installing agent skills from package assets..."

ASSETS_SKILLS=$("$PYTHON" -c "
import hybrid_coco, os
print(os.path.join(os.path.dirname(hybrid_coco.__file__), 'assets', 'skills'))
" 2>/dev/null)

SKILLS_DIR="$HOME/.claude/skills"
if [ -d "$ASSETS_SKILLS" ]; then
  mkdir -p "$SKILLS_DIR"
  for skill in "$ASSETS_SKILLS"/*; do
    [ -d "$skill" ] || continue
    [ -f "$skill/SKILL.md" ] || continue
    name=$(basename "$skill")
    rm -rf "$SKILLS_DIR/$name"
    cp -a "$skill" "$SKILLS_DIR/$name"
    info "  skill: $name"
  done
else
  warn "Package skills not found — skipped"
fi

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

# ── 6. Strip legacy ~/.claude/CLAUDE.md include ──────────────────────────────
# Instructions are project-local after `hc init`. Do not append to the user
# global CLAUDE.md / AGENTS.md.
info "Removing legacy global @hybrid-coco.md include if present..."
"$PYTHON" - << PYEOF
from pathlib import Path

home = Path.home()
awareness = home / ".claude" / "hybrid-coco.md"
if awareness.is_file():
    awareness.unlink()
    print("[hybrid-coco] removed ~/.claude/hybrid-coco.md")

claude_md = home / ".claude" / "CLAUDE.md"
if claude_md.is_file():
    text = claude_md.read_text(encoding="utf-8")
    kept = [line for line in text.splitlines(keepends=True) if line.strip() != "@hybrid-coco.md"]
    updated = "".join(kept)
    if updated != text:
        if not updated.strip():
            claude_md.unlink()
        else:
            claude_md.write_text(updated, encoding="utf-8")
        print("[hybrid-coco] removed @hybrid-coco.md from ~/.claude/CLAUDE.md")
PYEOF

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
info "Installation complete!"
echo ""
echo "  Next steps:"
echo "  hybrid-coco is self-contained: index, CLI, MCP, hooks, and skills."
echo "  1. Restart Claude Code (or reload the window)"
echo "  2. In any project: hc init   # index + project instruction pointer"
echo "  3. Use hc_* tools for code navigation"
echo "  4. Skills: hybrid-coco, /hc-init, /hc-search"
echo ""
echo "  To verify: hc --version"
echo ""
