#!/usr/bin/env python3
"""List section headers and action names from interface and global files."""

import re
import sys
from pathlib import Path

DEFAULT_ACTIONS_FOLDER = Path.home() / ".config" / "kanata" / "actions"

SECTION_RE = re.compile(r"^\s*;;\s*==\s+(.+?)\s*=+")
ACTION_RE = re.compile(r"^\s*(~?action_[^\s]+)")

folder = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ACTIONS_FOLDER

for path in sorted(folder.glob("global_*.kbd")) + sorted(folder.glob("app_*.kbd")):
    print(f"\n=== {path.name} ===")
    for line in path.read_text().splitlines():
        m = SECTION_RE.match(line)
        if m:
            print(line.strip())
            continue
        m = ACTION_RE.match(line)
        if m:
            print(f"  {m.group(1)}")
