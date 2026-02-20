#!/usr/bin/env python3
"""Dump unique action names from actions.kbd (strips ~ prefix)."""

import re
import sys
from pathlib import Path

DEFAULT_ACTIONS_FILE = Path.home() / ".config" / "kanata" / "actions" / "actions.kbd"

ACTION_RE = re.compile(r"^\s*~?(action_[^\s]+)")

path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ACTIONS_FILE

seen: set[str] = set()
for line in path.read_text().splitlines():
    m = ACTION_RE.match(line)
    if m and m.group(1) not in seen:
        seen.add(m.group(1))
        print(m.group(1))
