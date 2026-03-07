#!/usr/bin/env bash
#
# Orchestrates kanata sync: regenerates virtual keys and switch conditions,
# then syncs per-app action files with their interface definitions.
#
# Usage:
#   ./kanata_sync.sh          # incremental interface sync
#   ./kanata_sync.sh -f       # force full interface sync

set -euo pipefail

echo "=================== kanata_sync.sh ==================="
kanata_sync_apps.py -f
kanata_sync_all_apps_interfaces.sh "$@"
echo "======================================================"
