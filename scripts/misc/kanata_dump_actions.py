#!/usr/bin/env python3
"""Dump unique action names from interface and global files (strips ~ prefix)."""

import re
import sys
from pathlib import Path

DEFAULT_ACTIONS_FOLDER = Path.home() / ".config" / "kanata" / "actions"

ACTION_RE = re.compile(r"^\s*~?(action_[^\s]+)")

folder = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ACTIONS_FOLDER

seen: set[str] = set()
for path in sorted(folder.glob("app_*.kbd")) + sorted(folder.glob("global_*.kbd")):
    for line in path.read_text().splitlines():
        m = ACTION_RE.match(line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            print(m.group(1))
