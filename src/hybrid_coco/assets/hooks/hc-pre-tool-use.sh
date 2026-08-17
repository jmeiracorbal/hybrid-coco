#!/usr/bin/env bash
# hybrid-coco PreToolUse — delegates to `hc hook` so the marker gate is shared.
command -v hc >/dev/null 2>&1 || exit 0
exec hc hook claude pre-tool-use
