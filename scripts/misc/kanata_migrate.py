#!/usr/bin/env python3
"""
One-shot migration script: splits the monolithic actions.kbd and per-app
action files into the new modular interface/global file structure.

Target structure:
  actions/
    global_apps.kbd
    global_windows.kbd
    global_workspaces.kbd
    global_misc.kbd
    interface_replace.kbd
    interface_search.kbd
    interface_files.kbd
    interface_open.kbd
    interface_bookmarks.kbd
    interface_omni.kbd
    interface_mod_key.kbd
    interface_panes.kbd
    interface_tabs.kbd
    interface_groups.kbd
    interface_sessions.kbd
    interface_mod_physical.kbd
    apps/
      <app>_interface_<name>[.<priority>].kbd
      ...

Usage:
  ./kanata_migrate.py              # dry-run (prints what it would do)
  ./kanata_migrate.py --write      # actually write files
"""

import re
import sys
from pathlib import Path

KANATA_FOLDER = Path.home() / ".config" / "kanata"
ACTIONS_FOLDER = KANATA_FOLDER / "actions"
KANATA_FILE = KANATA_FOLDER / "kanata.kbd"

# Section-to-file mapping. Each entry: (start_line, end_line, target_file)
# Lines are 1-indexed (matching the file). Ranges are inclusive.
SECTION_MAP = [
    # (start, end, filename)
    (184, 186, "global_misc.kbd"),       # emojis
    (188, 200, "interface_replace.kbd"),  # replace
    (202, 220, "interface_search.kbd"),   # search
    (222, 238, "interface_files.kbd"),    # files/folders
    (240, 361, "global_apps.kbd"),        # apps
    (363, 616, "interface_bookmarks.kbd"),  # bookmarks (up to blank before opts)
    (618, 622, "global_misc.kbd"),       # opts
    (624, 644, "interface_open.kbd"),     # open
    (646, 965, "interface_omni.kbd"),     # omni
    (967, 1212, "interface_mod_key.kbd"),  # modA-modZ, mod;/'/,/.//
    (1217, 1238, "global_windows.kbd"),   # windows
    (1240, 1264, "global_workspaces.kbd"),  # workspaces + move
    (1266, 1610, "interface_panes.kbd"),  # panes + toggle/float/move/resize/swap/number/focus
    (1611, 1775, "interface_tabs.kbd"),   # tab + toggle/move/number
    (1776, 1941, "interface_groups.kbd"),  # !tab/groups + toggle/move/number
    (1942, 1951, "interface_sessions.kbd"),  # sessions
    (1953, 4498, "interface_mod_physical.kbd"),  # SFT, LCTL...!LMET+RSFT
]

# Regex to match @iface@ tagged actions in actions.kbd
IFACE_RE = re.compile(r"^\s*(~?action_[^\s]+)\s.*@iface@")

# Regex for app action filenames: actions_<app>[.<priority>].kbd
APP_FILE_RE = re.compile(r"^actions_([^.]+)(?:\.(\d+))?\.kbd$")

# Regex for app action lines: <app>_action_<name>  <implementation>
APP_ACTION_RE = re.compile(r"^\s*(\w+)_(action_[^\s]+)")

# Regex for ___TO_SET___ placeholder lines
TO_SET_RE = re.compile(r"^\s*;;\s*___TO_SET___\s+\w+_(action_\S+)")

# Regex for the @start@ marker
START_MARKER_RE = re.compile(r"^\s*;;\s*@start@")

# Regex for section headers (== ...)
SECTION_HEADER_RE = re.compile(r"^\s*;;\s*==+\s+")

# Regex for major section headers (=== ...)
MAJOR_SECTION_RE = re.compile(r"^\s*;;\s*===")

# Action name regex (both action_ and ~action_)
ACTION_NAME_RE = re.compile(r"^\s*(~?action_[^\s]+)")


def read_actions_file(path: Path) -> list[str]:
    """Read actions.kbd and return lines (1-indexed friendly)."""
    return path.read_text().splitlines()


def extract_sections(lines: list[str]) -> dict[str, list[str]]:
    """Extract file sections from actions.kbd based on the section map.

    Returns a dict mapping target filename -> list of content lines.
    Files appearing multiple times (global_misc.kbd) get their lines aggregated.
    """
    result: dict[str, list[str]] = {}

    for start, end, filename in SECTION_MAP:
        # Convert to 0-indexed
        section_lines = lines[start - 1 : end]

        if filename not in result:
            result[filename] = []
        else:
            # Add separator between aggregated sections
            result[filename].append("")

        result[filename].extend(section_lines)

    return result


def wrap_in_defvar(content_lines: list[str], is_interface: bool) -> str:
    """Wrap extracted lines in (defvar ...) with the @start@ marker for interfaces."""
    out = ["(defvar"]

    if is_interface:
        out.append("  ;; @start@ ====== DON'T REMOVE THIS LINE =================================")
        out.append("")

    for line in content_lines:
        out.append(line)

    out.append(")")
    return "\n".join(out) + "\n"


def build_action_to_interface_map(sections: dict[str, list[str]]) -> dict[str, str]:
    """Build a mapping from action short name to interface name.

    For interface files only, parse all action names (both action_ and ~action_)
    and map the short name (without action_/~action_ prefix) to the interface name.
    """
    mapping: dict[str, str] = {}

    for filename, content_lines in sections.items():
        if not filename.startswith("interface_"):
            continue

        # Extract interface name: interface_foo.kbd -> foo
        interface_name = filename.replace("interface_", "").replace(".kbd", "")

        for line in content_lines:
            # Check for autogen actions
            m = IFACE_RE.match(line)
            if m:
                action_name = m.group(1)  # e.g. action_tab_next or ~action_!tab_next
                # Strip ~ prefix and action_ prefix
                short = action_name.lstrip("~")
                if short.startswith("action_"):
                    short = short[len("action_"):]
                mapping[short] = interface_name
                continue

            # Check for non-autogen actions (global-like in interface files)
            m2 = ACTION_NAME_RE.match(line)
            if m2 and "@iface@" not in line:
                action_name = m2.group(1)
                short = action_name.lstrip("~")
                if short.startswith("action_"):
                    short = short[len("action_"):]
                mapping[short] = interface_name

    return mapping


def discover_app_files(actions_folder: Path) -> list[tuple[str, int | None, str]]:
    """Find all app action files.

    Returns list of (app_name, priority, filename) tuples.
    """
    result = []
    for p in sorted(actions_folder.glob("actions_*.kbd")):
        m = APP_FILE_RE.match(p.name)
        if m:
            app_name = m.group(1)
            priority = int(m.group(2)) if m.group(2) else None
            result.append((app_name, priority, p.name))
    return result


def parse_app_file(path: Path) -> tuple[str, list[tuple[list[str], str]], list[tuple[list[str], str]]]:
    """Parse an app file, extracting extra vars and action implementations.

    Returns:
        - app_name: extracted from filename
        - actions: list of (comments, line) for implemented/placeholder actions
        - extra_vars: list of (comments, line) for non-action variables
    """
    m = APP_FILE_RE.match(path.name)
    if not m:
        raise ValueError(f"Cannot parse filename: {path.name}")
    app_name = m.group(1)

    lines = path.read_text().splitlines()
    actions: list[tuple[list[str], str, str | None]] = []  # (comments, line, short_name_or_None)
    extra_vars: list[tuple[list[str], str]] = []

    pending_comments: list[str] = []
    in_defvar = False
    i = 0

    while i < len(lines):
        line = lines[i]

        if re.match(r"^\s*\(defvar\b", line):
            in_defvar = True
            i += 1
            continue

        if not in_defvar:
            i += 1
            continue

        # Closing paren
        if re.match(r"^\s*\)\s*$", line):
            break

        # Blank line resets pending comments
        if re.match(r"^\s*$", line):
            pending_comments = []
            i += 1
            continue

        # Comment line
        if re.match(r"^\s*;;", line):
            # Check if it's a TO_SET placeholder
            m_toset = TO_SET_RE.match(line)
            if m_toset:
                short_name = m_toset.group(1)
                if short_name.startswith("action_"):
                    short_name = short_name[len("action_"):]
                actions.append((pending_comments[:], line, short_name))
                pending_comments = []
            else:
                pending_comments.append(line)
            i += 1
            continue

        # App action line
        m_action = APP_ACTION_RE.match(line)
        if m_action and m_action.group(1) == app_name:
            action_full = m_action.group(2)  # action_tab_next
            short_name = action_full[len("action_"):]

            # Handle multi-line expressions
            full_line = line
            open_count = line.count("(") - line.count(")")
            while open_count > 0 and i + 1 < len(lines):
                i += 1
                full_line += "\n" + lines[i]
                open_count += lines[i].count("(") - lines[i].count(")")

            actions.append((pending_comments[:], full_line, short_name))
            pending_comments = []
            i += 1
            continue

        # Non-action variable (e.g. tmux_prefix A-b)
        if re.match(r"^\s*[^\s;(][^\s]*\s", line):
            full_line = line
            open_count = line.count("(") - line.count(")")
            while open_count > 0 and i + 1 < len(lines):
                i += 1
                full_line += "\n" + lines[i]
                open_count += lines[i].count("(") - lines[i].count(")")

            extra_vars.append((pending_comments[:], full_line))
            pending_comments = []
            i += 1
            continue

        i += 1

    return app_name, actions, extra_vars


def group_app_actions_by_interface(
    actions: list[tuple[list[str], str, str | None]],
    action_to_interface: dict[str, str],
) -> dict[str, list[tuple[list[str], str, str | None]]]:
    """Group app actions by their interface name.

    Actions not in any interface go under "_unmatched".
    """
    groups: dict[str, list[tuple[list[str], str, str | None]]] = {}

    for comments, line, short_name in actions:
        if short_name is None:
            interface = "_unmatched"
        else:
            interface = action_to_interface.get(short_name, "_unmatched")

        if interface not in groups:
            groups[interface] = []
        groups[interface].append((comments, line, short_name))

    return groups


def has_reversed_actions(interface_name: str, sections: dict[str, list[str]]) -> bool:
    """Check if an interface file contains ~ (reversed) actions."""
    filename = f"interface_{interface_name}.kbd"
    if filename not in sections:
        return False
    for line in sections[filename]:
        if re.match(r"^\s*~action_", line):
            return True
    return False


def write_app_interface_file(
    app_name: str,
    interface_name: str,
    actions: list[tuple[list[str], str, str | None]],
    extra_vars: list[tuple[list[str], str]] | None,
    priority: int | None,
    needs_priority: bool,
) -> tuple[str, str]:
    """Generate content for an app interface file.

    Returns (filename, content).
    """
    # Build filename
    if needs_priority and priority is not None:
        filename = f"{app_name}_interface_{interface_name}.{priority}.kbd"
    else:
        filename = f"{app_name}_interface_{interface_name}.kbd"

    out = ["(defvar"]

    # Add extra vars if this is the first interface file for the app
    if extra_vars:
        for var_comments, var_line in extra_vars:
            for c in var_comments:
                out.append(c)
            out.append(var_line)
        out.append("")

    # Add actions
    for comments, line, _short in actions:
        for c in comments:
            out.append(c)
        out.append(line)

    out.append(")")
    return filename, "\n".join(out) + "\n"


def update_kanata_kbd(kanata_path: Path) -> str:
    """Remove the old (include actions/actions.kbd) line from kanata.kbd."""
    lines = kanata_path.read_text().splitlines()
    out = []
    for line in lines:
        # Skip the old include line
        if re.match(r"^\s*\(include\s+actions/actions\.kbd\s*\)", line):
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def main() -> None:
    write_mode = "--write" in sys.argv

    print(f"Mode: {'WRITE' if write_mode else 'DRY-RUN'}")
    print()

    # ---- Step 1a: Split actions.kbd ----
    print("=== Step 1a: Split actions.kbd ===")
    actions_lines = read_actions_file(ACTIONS_FOLDER / "actions.kbd")
    sections = extract_sections(actions_lines)

    apps_dir = ACTIONS_FOLDER / "apps"

    for filename, content_lines in sorted(sections.items()):
        is_interface = filename.startswith("interface_")
        content = wrap_in_defvar(content_lines, is_interface)
        target = ACTIONS_FOLDER / filename
        print(f"  {filename}: {len(content_lines)} lines")
        if write_mode:
            target.write_text(content, encoding="utf-8")

    # ---- Step 1b: Build action-to-interface mapping ----
    print()
    print("=== Step 1b: Build action-to-interface map ===")
    action_to_interface = build_action_to_interface_map(sections)
    print(f"  {len(action_to_interface)} actions mapped to interfaces")

    # Also map global actions so we can identify unmatched
    global_actions: set[str] = set()
    for filename, content_lines in sections.items():
        if not filename.startswith("global_"):
            continue
        for line in content_lines:
            m = ACTION_NAME_RE.match(line)
            if m:
                short = m.group(1).lstrip("~")
                if short.startswith("action_"):
                    short = short[len("action_"):]
                global_actions.add(short)

    # ---- Step 1c: Split app files ----
    print()
    print("=== Step 1c: Split app files ===")
    app_files = discover_app_files(ACTIONS_FOLDER)
    print(f"  Found {len(app_files)} app files")

    if write_mode:
        apps_dir.mkdir(exist_ok=True)

    # Determine which interfaces have reversed actions (need priority in filename)
    interfaces_with_reversed: set[str] = set()
    for iface_name in set(action_to_interface.values()):
        if has_reversed_actions(iface_name, sections):
            interfaces_with_reversed.add(iface_name)
    print(f"  Interfaces with ~ actions: {interfaces_with_reversed}")

    for app_name, priority, orig_filename in app_files:
        print(f"\n  Processing {orig_filename}:")
        app_path = ACTIONS_FOLDER / orig_filename
        parsed_app, actions, extra_vars = parse_app_file(app_path)

        groups = group_app_actions_by_interface(actions, action_to_interface)

        # Sort interface names alphabetically
        sorted_interfaces = sorted(groups.keys())

        # Determine which interface file gets the extra vars
        # -> first alphabetically (excluding _unmatched)
        real_interfaces = [i for i in sorted_interfaces if i != "_unmatched"]
        extra_vars_target = real_interfaces[0] if real_interfaces else None

        for interface_name in sorted_interfaces:
            iface_actions = groups[interface_name]

            # Skip interfaces where ALL actions are TO_SET placeholders
            has_real_action = False
            for comments, line, short in iface_actions:
                if not re.match(r"^\s*;;", line.split("\n")[0]):
                    has_real_action = True
                    break
            # Actually, we need to keep all actions (even placeholders) for sync to work
            # But we can skip interfaces where no action is implemented
            # Let's keep all of them for the migration to be lossless

            # Determine if this interface needs priority
            needs_priority = interface_name in interfaces_with_reversed

            # Extra vars go in the first real interface file
            evars = extra_vars if interface_name == extra_vars_target else None

            if interface_name == "_unmatched":
                # Unmatched actions - put them in the alphabetically first interface
                if extra_vars_target:
                    # Merge into first interface
                    groups[extra_vars_target].extend(iface_actions)
                    print(f"    _unmatched: {len(iface_actions)} actions -> merged into {extra_vars_target}")
                continue

            fname, content = write_app_interface_file(
                app_name, interface_name, iface_actions, evars, priority, needs_priority
            )
            target = apps_dir / fname
            print(f"    {fname}: {len(iface_actions)} actions")
            if write_mode:
                target.write_text(content, encoding="utf-8")

    # ---- Step 1d: Update kanata.kbd ----
    print()
    print("=== Step 1d: Update kanata.kbd ===")
    new_kanata = update_kanata_kbd(KANATA_FILE)
    print("  Removed (include actions/actions.kbd) line")
    if write_mode:
        KANATA_FILE.write_text(new_kanata, encoding="utf-8")

    print()
    if write_mode:
        print("Migration complete! Files written.")
        print("Next steps:")
        print("  1. Run: ./scripts/kanata_sync_apps.py -f")
        print("  2. Run: ./scripts/kanata_sync_all_apps_interfaces.sh")
        print("  3. Test: Tab+r to reload kanata")
    else:
        print("DRY-RUN complete. Re-run with --write to apply changes.")


if __name__ == "__main__":
    main()
