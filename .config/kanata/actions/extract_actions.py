#!/usr/bin/env python3
import re
import sys

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <file.kbd>")
    sys.exit(1)

path = sys.argv[1]

action_re = re.compile(r"(action_\S+)")
comment_re = re.compile(r"^\s*;;.*")

seen_actions = set()

with open(path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()

        # Preserve comments
        if comment_re.match(line):
            if line[3:5] == "==":
                print(f"\n{line}")
            else:
                print(f"{line}")
            continue

        # Extract actions
        for match in action_re.findall(line):
            if match not in seen_actions:
                seen_actions.add(match)
                print(f"{match} _")
