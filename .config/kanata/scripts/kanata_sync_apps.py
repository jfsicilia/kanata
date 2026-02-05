#!/usr/bin/env python3

import re
from pathlib import Path

KANATA_EXT = "kbd"
KANATA_FOLDER = Path.home() / ".config" / "kanata"
KANATA_FILE = KANATA_FOLDER / "kanata.kbd"

ACTIONS_FOLDER = KANATA_FOLDER / "actions"
ACTIONS_FILE = ACTIONS_FOLDER / "actions.kbd"
ACTION_PREFIX = "action_"
ACTIONS_PREFIX = "actions_"
ACTION_START_RE = re.compile(r"^\s*(action_[^\s]+)\s.*switch")
ACTION_END = ")"
APP_ACTION_RE = re.compile(r"^\s*(\w+)_action_(.+?)\s")

AUTOGEN_SECTION_RE = re.compile(r";;\s+@@")

VK_LINE_RE = re.compile(r"\(\(input virtual vk_")


def find_apps():
    apps = []
    for p in ACTIONS_FOLDER.glob(f"{ACTIONS_PREFIX}*.{KANATA_EXT}"):
        name = p.stem[len(ACTIONS_PREFIX) :]
        apps.append(name)
    return sorted(apps)


def autogen_kanata_file(lines, apps):
    out = []

    for line in lines:
        out.append(line)

        # Autogen section reached?
        if not AUTOGEN_SECTION_RE.match(line):
            continue

        # Autogen with apps specific instructions.
        out.append(
            "\n;; Apps Virtual Keys =====================================================\n"
        )
        out.append("(defvirtualkeys\n")
        for app in apps:
            out.append(f"  vk_{app:<12} XX\n")
        out.append(")\n\n")

        out.append(
            ";; Actions & Apps' Actions ===============================================\n"
        )
        out.append(f"(include {ACTIONS_FILE.relative_to(KANATA_FOLDER)})\n")
        for app in apps:
            out.append(
                f"(include {ACTIONS_FOLDER.relative_to(KANATA_FOLDER)}/{ACTIONS_PREFIX}{app}.{KANATA_EXT})\n"
            )
        break

    return out


def load_app_actions(app):
    f"""
    Returns a set of action names (without '{ACTIONS_PREFIX}' prefix)
    """
    actions = set()
    path = ACTIONS_FOLDER / f"{ACTIONS_PREFIX}{app}.{KANATA_EXT}"
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
        short_name = action_name[len(ACTION_PREFIX) :]  # lctl+b

        out.append(line)
        i += 1

        # Skip old vk_* lines
        while i < len(lines) and (VK_LINE_RE.search(lines[i]) or not line.strip()):
            i += 1

        # Insert regenerated per-app bindings
        for app in apps:
            # print(f"{app} find {short_name}")
            if short_name in app_actions[app]:
                out.append(
                    f"    ((input virtual vk_{app})) ${app}_{ACTION_PREFIX}{short_name} break\n"
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
    apps = find_apps()

    if not apps:
        raise RuntimeError(
            f"No {ACTIONS_PREFIX}<app>.{KANATA_EXT} files found in {ACTIONS_FOLDER}"
        )

    text = KANATA_FILE.read_text().splitlines(keepends=True)
    result = autogen_kanata_file(text, apps)
    KANATA_FILE.write_text("".join(result), encoding="utf-8")

    result = sync_actions()
    ACTIONS_FILE.write_text("".join(result), encoding="utf-8")


if __name__ == "__main__":
    main()
