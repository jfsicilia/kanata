#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path

KANATA_EXT = "kbd"
KANATA_FOLDER = Path.home() / ".config" / "kanata"
KANATA_FILE = KANATA_FOLDER / "kanata.kbd"

ACTIONS_FOLDER = KANATA_FOLDER / "actions"
ACTIONS_FILE = ACTIONS_FOLDER / "actions.kbd"
ACTION_PREFIX = "action_"
ACTIONS_PREFIX = "actions_"
AUTOGEN_ACTION_RE = re.compile(r"^\s*(!action_[^\s]+|action_[^\s]+)\s.*@autogen@.*")
REVERSE_ACTION_FLAG = "!"
ACTION_END = ")"
APP_ACTION_RE = re.compile(r"^\s*(\w+)_action_(.+?)\s")

AUTOGEN_SECTION_RE = re.compile(r";;\s+@autogen@")

VK_LINE_RE = re.compile(r"\(\(input virtual vk_")

FILENAME_RE = re.compile(
    rf"^{re.escape(ACTIONS_PREFIX)}([^.]+)(?:\.(\d+))?\.{re.escape(KANATA_EXT)}$"
)


def find_apps():
    files_with_order = []

    for p in ACTIONS_FOLDER.glob(f"{ACTIONS_PREFIX}*.{KANATA_EXT}"):
        m = FILENAME_RE.match(p.name)
        if m:
            app_name = m.group(1)
            order_str = m.group(2)
            order = int(order_str) if order_str else None
            files_with_order.append((order, app_name, p.name))

    files_with_order.sort(key=lambda x: x[0] if x[0] is not None else 0)

    # devuelve solo los nombres de app
    return [(app_name, app_file) for _, app_name, app_file in files_with_order]


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
        for app_name, _ in apps:
            out.append(f"  vk_{app_name:<12} XX\n")
        out.append(")\n\n")

        out.append(
            ";; Actions & Apps' Actions ===============================================\n"
        )
        # out.append(f"(include {ACTIONS_FILE.relative_to(KANATA_FOLDER)})\n")
        for _, app_file in apps:
            out.append(
                f"(include {ACTIONS_FOLDER.relative_to(KANATA_FOLDER)}/{app_file})\n"
            )
        break

    return out


def load_app_actions(app_name, app_file):
    f"""
    Returns a set of action names (without '{ACTIONS_PREFIX}' prefix)
    """
    actions = set()
    path = ACTIONS_FOLDER / f"{app_file}"
    if not path.exists():
        return actions

    for line in path.read_text().splitlines():
        m = APP_ACTION_RE.match(line.strip())
        if m and m.group(1) == app_name:
            actions.add(m.group(2))
    return actions


def sync_actions():
    non_reversed_apps = find_apps()
    reversed_apps = non_reversed_apps[::-1]
    app_actions = {
        app_name: load_app_actions(app_name, app_file)
        for app_name, app_file in non_reversed_apps
    }

    lines = ACTIONS_FILE.read_text().splitlines(keepends=True)
    out = []

    i = 0
    while i < len(lines):
        line = lines[i]

        m = AUTOGEN_ACTION_RE.match(line)
        if not m:
            out.append(line)
            i += 1
            continue

        # ---- Process autogen of an action block ----
        action_name = m.group(1)  # action_lctl+b or !action_lctl+b
        if action_name.startswith(REVERSE_ACTION_FLAG):
            short_name = action_name[
                len(REVERSE_ACTION_FLAG) + len(ACTION_PREFIX) :
            ]  # lctl+b
            apps = reversed_apps
        else:
            short_name = action_name[len(ACTION_PREFIX) :]  # lctl+b
            apps = non_reversed_apps

        out.append(line)
        i += 1

        # Skip old vk_* lines
        while i < len(lines) and (VK_LINE_RE.search(lines[i]) or not line.strip()):
            i += 1

        # Insert regenerated per-app bindings
        for app_name, _ in apps:
            if short_name in app_actions[app_name]:
                out.append(
                    f"    ((input virtual vk_{app_name})) ${app_name}_{ACTION_PREFIX}{short_name} break\n"
                )

        # Copy all until action definition ends line. It usually copies
        # default binding of action:  () XX break / () _ break
        while i < len(lines):
            out.append(lines[i])
            line = lines[i]
            i += 1
            if line.strip().startswith(ACTION_END):
                break

    return out


def ask_confirmation():
    answer = (
        input(
            f"This will overwrite {KANATA_FILE} and {ACTIONS_FILE} files. Continue? [y/N]: "
        )
        .strip()
        .lower()
    )
    return answer in ("y", "yes")


def main(force: bool):
    apps = find_apps()

    if not apps:
        raise RuntimeError(
            f"No {ACTIONS_PREFIX}<app>.{KANATA_EXT} files found in {ACTIONS_FOLDER}"
        )

    if not force:
        if not ask_confirmation():
            print("Aborted.")
            sys.exit(1)

    # ---- write kanata file ----
    text = KANATA_FILE.read_text().splitlines(keepends=True)
    result = autogen_kanata_file(text, apps)
    KANATA_FILE.write_text("".join(result), encoding="utf-8")

    # ---- write actions file ----
    result = sync_actions()
    ACTIONS_FILE.write_text("".join(result), encoding="utf-8")

    print("Files updated successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize kanata configuration files based on detected app action files.\n\n"
            f"The script scans app action definitions in the {ACTIONS_FOLDER} folder. If an app "
            f"defines its own actions in a file named {ACTIONS_PREFIX}<app>.{KANATA_EXT}, "
            f"the app is added to {KANATA_FILE}, and app's actions are added to "
            f"{ACTIONS_FILE}."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite files without asking for confirmation",
    )

    args = parser.parse_args()
    main(force=args.force)
