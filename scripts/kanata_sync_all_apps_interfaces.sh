#!/usr/bin/env bash
#
# Sync all per-app action files with the shared app_*.kbd definitions.
#
# Finds every <app>_<name>[.<priority>].kbd file in per-app
# subdirectories of actions/ and runs kanata_sync_interfaces.py -w on
# each one, updating them in-place with any new or removed actions from
# the corresponding app_*.kbd file while preserving existing
# implementations and app-specific variables.
#
# Usage:
#   ./kanata_sync_all_apps_interfaces.sh
#
# Requirements:
#   - kanata_sync_interfaces.py must be in the same scripts folder.
#   - Python 3.10+ must be available.

set -euo pipefail
shopt -s nullglob # Avoid literal glob if no files match.

SCRIPT="kanata_sync_interfaces.py"
DIR="$HOME/.config/kanata/actions"

for file in "$DIR"/*/*.kbd; do
    echo "Processing: $file"
    "$SCRIPT" "-w" "$file"
done
