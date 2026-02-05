#!/usr/bin/env python3

import re
from pathlib import Path

ACTIONS_PREFIX = "actions_"
KANATA_FILE = "kanata.kbd"

SECTION_RE = re.compile(r";;\s+.+={3,}")


def find_apps():
    apps = []
    for p in Path(".").glob(f"{ACTIONS_PREFIX}*.kbd"):
        name = p.stem[len(ACTIONS_PREFIX) :]
        apps.append(name)
    return sorted(apps)


def rewrite_defvirtualkeys(lines, apps):
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)

        if line.strip().startswith(";; Apps Virtual Keys"):
            i += 1
            # copy until (defvirtualkeys
            while i < len(lines):
                out.append(lines[i])
                if lines[i].strip() == "(defvirtualkeys":
                    i += 1
                    break
                i += 1

            # inside defvirtualkeys
            while i < len(lines):
                line = lines[i]
                if line.strip().startswith(";;"):
                    out.append(line)
                elif line.strip() == ")":
                    # insert vk_<app> lines before closing
                    for app in apps:
                        out.append(f"  vk_{app:<12} XX\n")
                    out.append(line)
                    break
                i += 1
        i += 1
    return out


def rewrite_actions_section(lines, apps):
    out = []
    i = 0
    in_actions = False
    actions_written = False

    while i < len(lines):
        line = lines[i]

        # Detect start of Actions section
        if not in_actions and line.strip().startswith(";; Actions"):
            in_actions = True
            out.append(line)
            i += 1
            continue

        if in_actions:
            print(line)
            # Detect start of next section
            if SECTION_RE.match(line):
                if not actions_written:
                    out.append("(include actions.kbd)\n")
                    for app in apps:
                        out.append(f"(include actions_{app}.kbd)\n")
                    actions_written = True

                out.append(line)
                in_actions = False
                i += 1
                continue

            # Otherwise: skip everything, except comments, inside Actions section
            elif line.strip().startswith(";;"):
                out.append(line)
            i += 1
            continue

        # Normal line
        out.append(line)
        i += 1

    # EOF reached while still inside Actions section
    if in_actions and not actions_written:
        out.append("(include actions.kbd)\n")
        for app in apps:
            out.append(f"(include actions_{app}.kbd)\n")

    return out


def main():
    apps = find_apps()

    if not apps:
        raise RuntimeError("No actions_<app>.kbd files found")

    text = Path(KANATA_FILE).read_text().splitlines(keepends=True)

    text = rewrite_defvirtualkeys(text, apps)
    text = rewrite_actions_section(text, apps)

    print("".join(text))


if __name__ == "__main__":
    main()
