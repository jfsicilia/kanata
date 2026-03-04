#!/usr/bin/env python3
"""
Synchronize kanata configuration files based on detected per-app action files.

This script scans per-app subdirectories under actions/ (e.g. actions/nvim/,
actions/chrome/) for app-specific action files
(<app>_<name>[.<priority>].kbd) and performs two operations:

  1. Regenerates the bottom of kanata.kbd (below the @autogen@ marker):
     - Defines a virtual key (vk_<app>) for each detected app.
     - Adds include statements for each per-app action file.

  2. Regenerates the per-app switch conditions inside each app_*.kbd:
     - For each @autogen@-tagged action, inserts ((input virtual vk_<app>))
       conditions for apps that implement that action.
     - Actions prefixed with ~ get the app order reversed, enabling
       alternate priority when apps overlap (e.g. nvim inside tmux).

App priority per interface is controlled by the optional numeric index in
the filename (e.g. nvim_groups.1.kbd = highest priority for groups
interface). Lower numbers come first in switch conditions; files without
an index default to 0.

Usage:
  # Interactive (asks for confirmation before writing):
  ./kanata_sync_apps.py

  # Skip confirmation:
  ./kanata_sync_apps.py -f

  # Use custom paths:
  ./kanata_sync_apps.py -f --actions-folder /path/to/actions
"""

import argparse
import re
import sys
from pathlib import Path

KANATA_EXT = "kbd"

DEFAULT_KANATA_FOLDER = (
    Path.home() / ".config" / "kanata_interfaces" / ".config" / "kanata"
)
# DEFAULT_KANATA_FOLDER = Path.home() / ".config" / "kanata"
DEFAULT_KANATA_FILE = DEFAULT_KANATA_FOLDER / "kanata.kbd"
DEFAULT_ACTIONS_FOLDER = DEFAULT_KANATA_FOLDER / "actions"

GLOBAL_PREFIX = "global_"
APP_PREFIX = "app_"
ACTION_PREFIX = "action_"

# Matches an @autogen@-tagged action definition in an interface file, e.g.:
#   action_lctl+a (t! unmod_all (switch ;;@autogen@
#   ~action_tab_next (t! unmod_all (switch ;;@autogen@
AUTOGEN_ACTION_RE = re.compile(r"^\s*(~?action_[^\s]+)\s.*@autogen@.*")

REVERSE_ACTION_FLAG = "~"
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

# Matches the interface name and optional priority from a per-app filename
# after stripping the <app>_ prefix, e.g.:
#   "omni.kbd"       -> iface="omni", priority=None
#   "groups.1.kbd"   -> iface="groups", priority="1"
IFACE_PRIORITY_RE = re.compile(r"^(\w+)(?:\.(\d+))?\.kbd$")

# def find_apps(actions_folder: Path) -> list[tuple[str, str]]:
#     """Discover app action files and return them sorted by priority.
#
#     Scans the actions folder for files matching the pattern
#     actions_<app>[.<priority>].kbd. Files are sorted by priority index
#     (lower numbers first; files without an index default to 0).
#
#     Args:
#         actions_folder: Path to the folder containing action files.
#
#     Returns:
#         List of (app_name, filename) tuples sorted by priority.
#         Example: [("nvim", "actions_nvim.1.kbd"), ("chrome", "actions_chrome.4.kbd")]
#     """
#     files_with_order: list[tuple[int | None, str, str]] = []
#
#     for p in actions_folder.glob(f"{ACTIONS_PREFIX}*.{KANATA_EXT}"):
#         m = FILENAME_RE.match(p.name)
#         if m:
#             app_name: str = m.group(1)
#             order_str: str = m.group(2)
#             order: int | None = int(order_str) if order_str else None
#             files_with_order.append((order, app_name, p.name))
#
#     files_with_order.sort(key=lambda x: x[0] if x[0] is not None else 0)
#
#     return [(app_name, app_file) for _, app_name, app_file in files_with_order]


def find_apps(
    actions_folder: Path,
) -> tuple[set[str], dict[str, list[tuple[str, str, int]]]]:
    """Discover per-app action files from per-app subdirectories.

    Scans subdirectories of actions_folder for files matching the pattern
    <app>_<name>[.<priority>].kbd.

    Args:
        actions_folder: Path to the actions folder containing per-app subdirs.

    Returns:
        Tuple of:
          - app_list: List of (app_name, global_priority) tuples sorted by
            minimum priority across all interfaces. Used for virtual key
            generation and overall app ordering.
          - per_interface: Dict mapping interface_name -> list of
            (app_name, filename, priority) tuples sorted by priority.
    """
    apps: set[str] = set()
    iface2app: dict[str, list[tuple[str, str, int]]] = {}

    for app_dir in actions_folder.iterdir():
        if not app_dir.is_dir():
            continue

        app = app_dir.name
        apps.add(app)

        # Find all interfaces that app implements.
        prefix = f"{app}_"
        for entry in app_dir.glob(f"*.{KANATA_EXT}"):
            filename = entry.name
            if not filename.startswith(prefix):
                continue
            remainder = filename[len(prefix) :]
            m = IFACE_PRIORITY_RE.match(remainder)
            if not m:
                continue

            # Pick the interface name and the priority from the filename
            interface = m.group(1)
            priority: int = int(m.group(2)) if m.group(2) else -1

            # Store implementation for that interface.
            if interface not in iface2app:
                iface2app[interface] = []
            iface2app[interface].append((app, filename, priority))

    # Sort per-interface lists by priority
    for interface in iface2app:
        iface2app[interface].sort(key=lambda x: x[2])

    return (apps, iface2app)


def autogen_kanata_file(
    lines: list[str],
    apps: set[str],
    iface2app: dict[str, list[tuple[str, str, int]]],
    actions_folder: Path,
    kanata_folder: Path,
) -> list[str]:
    """Regenerate the autogen section of kanata.kbd.

    Copies all lines up to and including the @autogen@ marker, then
    appends:
      - Include statements for global_*.kbd files.
      - Include statements for app_*.kbd files.
      - A defvirtualkeys block with one vk_<app> per detected app.
      - Include statements for each per-app action file.

    Args:
        lines: Original kanata.kbd content as a list of lines (with newlines).
        app_list: List of (app_name, priority) tuples from find_apps.
        per_interface: Dict mapping interface_name -> app file list.
        actions_folder: Path to the actions folder.
        kanata_folder: Path to the kanata config root.

    Returns:
        List of output lines (with newlines) forming the complete kanata.kbd.
    """
    rel_actions = actions_folder.relative_to(kanata_folder)
    out: list[str] = []

    for line in lines:
        out.append(line)

        if not AUTOGEN_SECTION_RE.match(line):
            continue

        # ---- Virtual keys ----
        out.append(
            "\n;; Apps Virtual Keys =====================================================\n"
        )
        out.append("(defvirtualkeys\n")
        for app in apps:
            out.append(f"  vk_{app:<12} XX\n")
        out.append(")\n")

        # ---- Per-app action files ----
        out.append(
            "\n;; Apps' Actions ========================================================\n"
        )
        # Collect all app files
        all_app_files: list[tuple[str, str]] = []
        for iface_apps in iface2app.values():
            for app, filename, _ in iface_apps:
                all_app_files.append((app, filename))
        all_app_files.sort()

        for app, filename in all_app_files:
            out.append(f"(include {rel_actions}/{app}/{filename})\n")
        break

    return out


def load_app_actions(app_name: str, app_file: str, actions_folder: Path) -> set[str]:
    """Load action short names implemented by an app from a per-app file.

    Reads a per-app action file and extracts the short names (without the
    "action_" prefix) of all actions the app implements.

    Args:
        app_name: App name (e.g. "nvim") used to filter matching lines.
        app_file: Filename of the per-app action file.
        actions_folder: Path to the actions folder (parent of app subdirs).

    Returns:
        Set of action short names (e.g. {"tab_next", "pane_left", ...}).
    """
    actions: set[str] = set()
    path = actions_folder / app_name / app_file
    if not path.exists():
        return actions

    for line in path.read_text().splitlines():
        m = APP_ACTION_RE.match(line.strip())
        if m and m.group(1) == app_name:
            actions.add(m.group(2))
    return actions


def sync_interface_actions(
    interface_file: Path,
    interface_name: str,
    iface2app: dict[str, list[tuple[str, str, int]]],
    actions_folder: Path,
) -> list[str]:
    """Regenerate switch conditions in a single shared action file.

    For each @autogen@-tagged action, replaces the per-app virtual key
    conditions with freshly generated ones based on which apps actually
    implement each action in this interface.

    Actions prefixed with ~ use reversed app order.

    Args:
        interface_file: Path to the app_*.kbd file.
        interface_name: Name of the interface (e.g. "omni", "panes").
        per_interface: Dict from find_apps with per-interface app lists.
        actions_folder: Path to the actions folder (parent of app subdirs).

    Returns:
        List of output lines (with newlines) forming the updated action file.
    """
    apps = iface2app.get(interface_name, [])

    # Build ordered app lists for normal and reversed
    non_reversed_apps = [(a, f) for a, f, _ in apps]
    reversed_apps = non_reversed_apps[::-1]

    # Load implemented actions for each app in this interface
    app_actions: dict[str, set[str]] = {}
    for app, filename in non_reversed_apps:
        app_actions[app] = load_app_actions(app, filename, actions_folder)

    lines = interface_file.read_text().splitlines(keepends=True)
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
        action_name = m.group(1)  # action_lctl+b or ~action_lctl+b
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
        for app, _ in apps:
            if short_name in app_actions.get(app, set()):
                out.append(
                    f"    ((input virtual vk_{app})) ${app}_{ACTION_PREFIX}{short_name} break\n"
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


def ask_confirmation(kanata_file: Path, actions_folder: Path) -> bool:
    """Prompt the user for confirmation before overwriting files.

    Args:
        kanata_file: Path to the kanata.kbd file that will be overwritten.
        actions_folder: Path to the actions folder.

    Returns:
        True if the user confirms, False otherwise.
    """
    answer = (
        input(
            f"This will overwrite {kanata_file} and app_*.kbd files in {actions_folder}. Continue? [y/N]: "
        )
        .strip()
        .lower()
    )
    return answer in ("y", "yes")


def main(
    force: bool,
    kanata_file: Path,
    actions_folder: Path,
) -> None:
    """Run the sync process.

    Args:
        force: If True, skip confirmation prompt.
        kanata_file: Path to kanata.kbd.
        actions_folder: Path to the actions folder.
    """
    apps, iface2app = find_apps(actions_folder)

    if not apps:
        raise RuntimeError(
            f"No <app>_<name>.{KANATA_EXT} files found in {actions_folder} subdirectories"
        )

    if not force:
        if not ask_confirmation(kanata_file, actions_folder):
            print("Aborted.")
            sys.exit(1)

    # ---- write kanata file ----
    kanata_folder = kanata_file.parent
    text = kanata_file.read_text().splitlines(keepends=True)
    result = autogen_kanata_file(text, apps, iface2app, actions_folder, kanata_folder)
    kanata_file.write_text("".join(result), encoding="utf-8")

    # ---- write actions/<app>/<app>_*.kbd files ----
    iface_files = actions_folder.glob(f"{APP_PREFIX}*.{KANATA_EXT}")
    for iface_path in iface_files:
        iface_name = iface_path.stem.removeprefix(APP_PREFIX)
        result = sync_interface_actions(
            iface_path, iface_name, iface2app, actions_folder
        )
        iface_path.write_text("".join(result), encoding="utf-8")

    print("Files updated successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize kanata configuration files based on detected per-app action files.\n\n"
            "Scans per-app subdirectories of the actions folder for files named\n"
            "<app>_<name>[.<priority>].kbd. For each app found:\n"
            "  - A virtual key (vk_<app>) and includes are added to kanata.kbd.\n"
            "  - Switch conditions are regenerated in each app_*.kbd file.\n\n"
            "Usage:\n"
            "  ./kanata_sync_apps.py -f\n"
            "  ./kanata_sync_apps.py -f --actions-folder /path/to/actions"
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
        "--actions-folder",
        type=Path,
        default=DEFAULT_ACTIONS_FOLDER,
        help=f"Path to the actions folder (default: {DEFAULT_ACTIONS_FOLDER}).",
    )

    args = parser.parse_args()
    main(
        force=args.force,
        kanata_file=args.kanata_file,
        actions_folder=args.actions_folder,
    )
