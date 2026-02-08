#!/usr/bin/env bash

set -euo pipefail
shopt -s nullglob

SCRIPT="$HOME/.config/kanata/scripts/kanata_sync_interfaces.py"
DIR="$HOME/.config/kanata/actions"

for file in "$DIR"/actions_*.kbd; do
  echo "Processing: $file"
  "$SCRIPT" "-w" "$file"
done
