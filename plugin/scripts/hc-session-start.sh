#!/usr/bin/env bash
# hybrid-coco SessionStart — incremental update + hc_* reminder when the
# project marker is valid. does not write instruction files.
command -v hc >/dev/null 2>&1 || exit 0
exec hc hook claude session-start
