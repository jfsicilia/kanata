#!/usr/bin/env python3

import re
from pathlib import Path

ACTIONS_PREFIX = "actions_"
ACTION_START_RE = re.compile(r"^\s*(action_[^\s]+)\s.*switch")
ACTION_END = ")"
APP_ACTION_RE = re.compile(r"^\s*(\w+)_action_(.+?)\s")

VK_LINE_RE = re.compile(r"\(\(input virtual vk_")
# DEFAULT_LINE_RE = re.compile(r"\(\)\s+(XX|_)\s+break")

ACTIONS_FILE = Path("actions.kbd")


def find_apps():
    apps = []
    for p in Path(".").glob(f"{ACTIONS_PREFIX}*.kbd"):
        name = p.stem[len(ACTIONS_PREFIX) :]
        apps.append(name)
    return sorted(apps)


def load_app_actions(app):
    """
    Returns a set of action names (without 'action_' prefix)
    """
    actions = set()
    path = Path(f"actions_{app}.kbd")
    if not path.exists():
        return actions

    for line in path.read_text().splitlines():
        m = APP_ACTION_RE.match(line.strip())
        if m and m.group(1) == app:
            actions.add(m.group(2))
    return actions


def sync_actions():
    apps = find_apps()
    app_actions = {app: load_app_actions(app) for app in apps}

    lines = ACTIONS_FILE.read_text().splitlines(keepends=True)
    out = []

    i = 0
    while i < len(lines):
        line = lines[i]
        m = ACTION_START_RE.match(line)

        if not m:
            out.append(line)
            i += 1
            continue

        # ---- Start of an action block ----
        action_name = m.group(1)  # action_lctl+b
        short_name = action_name[len("action_") :]  # lctl+b

        out.append(line)
        i += 1

        # Skip old vk_* lines
        while i < len(lines) and (VK_LINE_RE.search(lines[i]) or not line.strip()):
            i += 1

        # Insert regenerated per-app bindings
        for app in apps:
            if short_name in app_actions[app]:
                out.append(
                    f"    ((input virtual vk_{app})) ${app}_action_{short_name} break\n"
                )

        # Copy default line: () XX break / () _ break
        while i < len(lines) and lines[i].strip().startswith(ACTION_END):
            out.append(lines[i])
            i += 1
        # ACTION_END
        out.append(lines[i])
        i += 1

    return out


def main():
    result = sync_actions()
    ACTIONS_FILE.write_text("".join(result), encoding="utf-8")


if __name__ == "__main__":
    main()
