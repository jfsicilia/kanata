#!/usr/bin/env python3
"""Remove all comment and blank lines from an actions_<app>.kbd file."""

import re
import sys
from pathlib import Path

COMMENT_RE = re.compile(r"^\s*;;")
EMPTY_RE = re.compile(r"^\s*$")

if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} <actions_app.kbd>", file=sys.stderr)
    sys.exit(1)

for line in Path(sys.argv[1]).read_text().splitlines():
    if not COMMENT_RE.match(line) and not EMPTY_RE.match(line):
        print(line)
