#!/usr/bin/env python3
"""List section headers and action names from actions.kbd."""

import re
import sys
from pathlib import Path

DEFAULT_ACTIONS_FILE = Path.home() / ".config" / "kanata" / "actions" / "actions.kbd"

SECTION_RE = re.compile(r"^\s*;;\s*==\s+(.+?)\s*=+")
ACTION_RE = re.compile(r"^\s*(~?action_[^\s]+)")

path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ACTIONS_FILE

for line in path.read_text().splitlines():
    m = SECTION_RE.match(line)
    if m:
        print(line.strip())
        continue
    m = ACTION_RE.match(line)
    if m:
        print(f"  {m.group(1)}")
