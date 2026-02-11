#!/usr/bin/env bash
#
# Sync all app action files with the shared actions.kbd interfaces.
#
# Finds every actions_<app>[.<priority>].kbd file in the actions folder
# and runs kanata_sync_interfaces.py -w on each one, updating them
# in-place with any new or removed actions from actions.kbd while
# preserving existing implementations and app-specific variables.
#
# Usage:
#   ./kanata_sync_all_apps_interfaces.sh
#
# Requirements:
#   - kanata_sync_interfaces.py must be in the same scripts folder.
#   - Python 3.10+ must be available.

set -euo pipefail
shopt -s nullglob  # Avoid literal glob if no files match.

SCRIPT="$HOME/.config/kanata/scripts/kanata_sync_interfaces.py"
DIR="$HOME/.config/kanata/actions"

for file in "$DIR"/actions_*.kbd; do
  echo "Processing: $file"
  "$SCRIPT" "-w" "$file"
done
