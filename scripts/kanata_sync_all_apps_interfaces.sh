#!/usr/bin/env bash
#
# Sync all per-app action files with the shared actions_*.iface.kbd definitions.
#
# Finds every <app>_<name>[.<priority>].kbd file in per-app
# subdirectories of actions/ and runs kanata_sync_interfaces.py -w on
# each one, updating them in-place with any new or removed actions from
# the corresponding actions_*.iface.kbd file while preserving existing
# implementations and app-specific variables.
#
# By default, only processes files that changed since the last successful
# run (incremental mode). Use -f/--force for a full sync.
#
# Usage:
#   ./kanata_sync_all_apps_interfaces.sh        # incremental
#   ./kanata_sync_all_apps_interfaces.sh -f     # full (force all)
#
# Requirements:
#   - kanata_sync_interfaces.py must be in the same scripts folder.
#   - Python 3.10+ must be available.

set -euo pipefail
shopt -s nullglob # Avoid literal glob if no files match.

SCRIPT="kanata_sync_interfaces.py"
DIR="$HOME/.config/kanata/actions"
SENTINEL="$DIR/.last_sync_interfaces"

force=false
if [[ "${1:-}" == "-f" || "${1:-}" == "--force" ]]; then
    force=true
fi

# Full sync if forced or sentinel doesn't exist.
if $force || [[ ! -f "$SENTINEL" ]]; then
    for file in "$DIR"/*/*.kbd; do
        echo "Processing: $file"
        "$SCRIPT" "-w" "$file"
    done
    touch "$SENTINEL"
    exit 0
fi

# -- Incremental mode --

# Collect set of per-app files to process (deduped via associative array).
declare -A to_process
found=false

# 1. Changed iface files → reprocess all per-app files for those interfaces.
for iface_file in "$DIR"/actions_*.iface.kbd; do
    [[ "$iface_file" -nt "$SENTINEL" ]] || continue
    # Extract interface name: actions_omni.iface.kbd → omni
    basename="${iface_file##*/}"
    iface_name="${basename#actions_}"
    iface_name="${iface_name%.iface.kbd}"
    # Add all per-app files matching this interface.
    for app_file in "$DIR"/*/*_"${iface_name}".kbd "$DIR"/*/*_"${iface_name}".*.kbd; do
        to_process["$app_file"]=1
        found=true
    done
done

# 2. Directly changed per-app files.
for app_file in "$DIR"/*/*.kbd; do
    if [[ "$app_file" -nt "$SENTINEL" ]]; then
        to_process["$app_file"]=1
        found=true
    fi
done

# Process collected files.
if ! $found; then
    echo "Nothing to sync."
else
    for file in "${!to_process[@]}"; do
        echo "Processing: $file"
        "$SCRIPT" "-w" "$file"
    done
fi

touch "$SENTINEL"
