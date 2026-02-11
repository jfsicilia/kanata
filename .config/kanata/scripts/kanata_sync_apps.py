#!/usr/bin/env python3
"""
Synchronize kanata configuration files based on detected app action files.

This script scans the actions folder for app-specific action files
(actions_<app>[.<priority>].kbd) and performs two operations:

  1. Regenerates the bottom of kanata.kbd (below the @autogen@ marker):
     - Defines a virtual key (vk_<app>) for each detected app.
     - Adds include statements for each app's action file.

  2. Regenerates the per-app switch conditions inside actions.kbd:
     - For each @autogen@-tagged action, inserts ((input virtual vk_<app>))
       conditions for apps that implement that action.
     - Actions prefixed with ! get the app order reversed, enabling
       alternate priority when apps overlap (e.g. nvim inside tmux).

App priority is controlled by the optional numeric index in the filename
(e.g. actions_nvim.1.kbd = highest priority). Lower numbers come first
in switch conditions; apps without an index default to 0.

Usage:
  # Interactive (asks for confirmation before writing):
  ./kanata_sync_apps.py

  # Skip confirmation:
  ./kanata_sync_apps.py -f

  # Use custom paths:
  ./kanata_sync_apps.py -f --actions-folder /path/to/actions --actions-file /path/to/actions.kbd
"""

import argparse
import re
import sys
from pathlib import Path

KANATA_EXT = "kbd"

DEFAULT_KANATA_FOLDER = Path.home() / ".config" / "kanata"
DEFAULT_KANATA_FILE = DEFAULT_KANATA_FOLDER / "kanata.kbd"
DEFAULT_ACTIONS_FOLDER = DEFAULT_KANATA_FOLDER / "actions"
DEFAULT_ACTIONS_FILE = DEFAULT_ACTIONS_FOLDER / "actions.kbd"

ACTION_PREFIX = "action_"
ACTIONS_PREFIX = "actions_"

# Matches an @autogen@-tagged action definition in actions.kbd, e.g.:
#   action_lctl+a (t! unmod_all (switch ;;@autogen@
#   !action_tab_next (t! unmod_all (switch ;;@autogen@
AUTOGEN_ACTION_RE = re.compile(r"^\s*(!action_[^\s]+|action_[^\s]+)\s.*@autogen@.*")

REVERSE_ACTION_FLAG = "!"
ACTION_END = ")"

# Matches an app-prefixed action in an app file, e.g.:
#   nvim_action_tab_next  (macro esc ...)
# group(1) = app name, group(2) = action short name (e.g. "tab_next")
APP_ACTION_RE = re.compile(r"^\s*(\w+)_action_(.+?)\s")

# Matches the @autogen@ section marker in kanata.kbd.
AUTOGEN_SECTION_RE = re.compile(r";;\s+@autogen@")

# Matches a virtual key input condition line, e.g.:
#   ((input virtual vk_nvim)) $nvim_action_tab_next break
VK_LINE_RE = re.compile(r"\(\(input virtual vk_")

# Matches app action filenames, e.g.:
#   actions_nvim.1.kbd  ->  group(1)="nvim", group(2)="1"
#   actions_chrome.kbd  ->  group(1)="chrome", group(2)=None
FILENAME_RE = re.compile(
    rf"^{re.escape(ACTIONS_PREFIX)}([^.]+)(?:\.(\d+))?\.{re.escape(KANATA_EXT)}$"
)


def find_apps(actions_folder: Path) -> list[tuple[str, str]]:
    """Discover app action files and return them sorted by priority.

    Scans the actions folder for files matching the pattern
    actions_<app>[.<priority>].kbd. Files are sorted by priority index
    (lower numbers first; files without an index default to 0).

    Args:
        actions_folder: Path to the folder containing action files.

    Returns:
        List of (app_name, filename) tuples sorted by priority.
        Example: [("nvim", "actions_nvim.1.kbd"), ("chrome", "actions_chrome.4.kbd")]
    """
    files_with_order: list[tuple[int | None, str, str]] = []

    for p in actions_folder.glob(f"{ACTIONS_PREFIX}*.{KANATA_EXT}"):
        m = FILENAME_RE.match(p.name)
        if m:
            app_name: str = m.group(1)
            order_str: str = m.group(2)
            order: int | None = int(order_str) if order_str else None
            files_with_order.append((order, app_name, p.name))

    files_with_order.sort(key=lambda x: x[0] if x[0] is not None else 0)

    return [(app_name, app_file) for _, app_name, app_file in files_with_order]


def autogen_kanata_file(
    lines: list[str],
    apps: list[tuple[str, str]],
    actions_folder: Path,
    kanata_folder: Path,
) -> list[str]:
    """Regenerate the autogen section of kanata.kbd.

    Copies all lines up to and including the @autogen@ marker, then
    appends:
      - A defvirtualkeys block with one vk_<app> per detected app.
      - Include statements for each app's action file.

    Args:
        lines: Original kanata.kbd content as a list of lines (with newlines).
        apps: List of (app_name, filename) tuples from find_apps.
        actions_folder: Path to the actions folder (for building include paths).
        kanata_folder: Path to the kanata config root (for relative path computation).

    Returns:
        List of output lines (with newlines) forming the complete kanata.kbd.
    """
    out: list[str] = []

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
        for _, app_file in apps:
            out.append(
                f"(include {actions_folder.relative_to(kanata_folder)}/{app_file})\n"
            )
        break

    return out


def load_app_actions(app_name: str, app_file: str, actions_folder: Path) -> set[str]:
    """Load action short names implemented by an app.

    Reads an app action file and extracts the short names (without the
    "action_" prefix) of all actions the app implements.

    Args:
        app_name: App name (e.g. "nvim") used to filter matching lines.
        app_file: Filename of the app action file (e.g. "actions_nvim.1.kbd").
        actions_folder: Path to the actions folder.

    Returns:
        Set of action short names (e.g. {"tab_next", "pane_left", ...}).
    """
    actions: set[str] = set()
    path = actions_folder / f"{app_file}"
    if not path.exists():
        return actions

    for line in path.read_text().splitlines():
        m = APP_ACTION_RE.match(line.strip())
        if m and m.group(1) == app_name:
            actions.add(m.group(2))
    return actions


def sync_actions(actions_file: Path, actions_folder: Path) -> list[str]:
    """Regenerate switch conditions in actions.kbd.

    For each @autogen@-tagged action in actions.kbd, replaces the
    per-app virtual key conditions with freshly generated ones based
    on which apps actually implement each action.

    Actions prefixed with ! use reversed app order.

    Args:
        actions_file: Path to the shared actions.kbd file.
        actions_folder: Path to the folder containing app action files.

    Returns:
        List of output lines (with newlines) forming the updated actions.kbd.
    """
    non_reversed_apps = find_apps(actions_folder)
    reversed_apps = non_reversed_apps[::-1]
    app_actions = {
        app_name: load_app_actions(app_name, app_file, actions_folder)
        for app_name, app_file in non_reversed_apps
    }

    lines = actions_file.read_text().splitlines(keepends=True)
    out: list[str] = []

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


def ask_confirmation(kanata_file: Path, actions_file: Path) -> bool:
    """Prompt the user for confirmation before overwriting files.

    Args:
        kanata_file: Path to the kanata.kbd file that will be overwritten.
        actions_file: Path to the actions.kbd file that will be overwritten.

    Returns:
        True if the user confirms, False otherwise.
    """
    answer = (
        input(
            f"This will overwrite {kanata_file} and {actions_file} files. Continue? [y/N]: "
        )
        .strip()
        .lower()
    )
    return answer in ("y", "yes")


def main(
    force: bool,
    kanata_file: Path,
    actions_file: Path,
    actions_folder: Path,
) -> None:
    """Run the sync process.

    Args:
        force: If True, skip confirmation prompt.
        kanata_file: Path to kanata.kbd.
        actions_file: Path to actions.kbd.
        actions_folder: Path to the actions folder.
    """
    apps: list[tuple[str, str]] = find_apps(actions_folder)

    if not apps:
        raise RuntimeError(
            f"No {ACTIONS_PREFIX}<app>.{KANATA_EXT} files found in {actions_folder}"
        )

    if not force:
        if not ask_confirmation(kanata_file, actions_file):
            print("Aborted.")
            sys.exit(1)

    # ---- write kanata file ----
    kanata_folder = kanata_file.parent
    text = kanata_file.read_text().splitlines(keepends=True)
    result = autogen_kanata_file(text, apps, actions_folder, kanata_folder)
    _ = kanata_file.write_text("".join(result), encoding="utf-8")

    # ---- write actions file ----
    result = sync_actions(actions_file, actions_folder)
    _ = actions_file.write_text("".join(result), encoding="utf-8")

    print("Files updated successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize kanata configuration files based on detected app action files.\n\n"
            f"Scans app action definitions in the actions folder for files named\n"
            f"{ACTIONS_PREFIX}<app>[.<priority>].{KANATA_EXT}. For each app found:\n"
            f"  - A virtual key (vk_<app>) and include are added to kanata.kbd.\n"
            f"  - Switch conditions are regenerated in actions.kbd.\n\n"
            "Usage:\n"
            "  ./kanata_sync_apps.py -f\n"
            "  ./kanata_sync_apps.py -f --actions-folder /path/to/actions\n"
            "  ./kanata_sync_apps.py -f --actions-file /path/to/actions.kbd --kanata-file /path/to/kanata.kbd"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    _ = parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite files without asking for confirmation.",
    )

    _ = parser.add_argument(
        "--kanata-file",
        type=Path,
        default=DEFAULT_KANATA_FILE,
        help=f"Path to kanata.kbd (default: {DEFAULT_KANATA_FILE}).",
    )

    _ = parser.add_argument(
        "--actions-file",
        type=Path,
        default=DEFAULT_ACTIONS_FILE,
        help=f"Path to actions.kbd (default: {DEFAULT_ACTIONS_FILE}).",
    )

    _ = parser.add_argument(
        "--actions-folder",
        type=Path,
        default=DEFAULT_ACTIONS_FOLDER,
        help=f"Path to the actions folder (default: {DEFAULT_ACTIONS_FOLDER}).",
    )

    args = parser.parse_args()
    main(
        force=args.force,
        kanata_file=args.kanata_file,
        actions_file=args.actions_file,
        actions_folder=args.actions_folder,
    )
