#!/usr/bin/env python3
"""
Sync action interfaces from a shared actions.kbd into an app-specific
actions file (e.g. actions_chrome.4.kbd).

When the target file already exists, the script preserves:
  - Existing action implementations (uncommented action lines).
  - Non-action variable definitions (e.g. tmux_prefix).
  - App-specific actions not present in actions.kbd.
Actions that exist in actions.kbd but are missing from the app file are
added as commented-out placeholders.

Usage:
  # Dry-run (prints to stdout):
  ./kanata_sync_interfaces.py actions/actions_tmux.98.kbd

  # Write changes to the file:
  ./kanata_sync_interfaces.py -w actions/actions_tmux.98.kbd

  # Use a custom actions.kbd location:
  ./kanata_sync_interfaces.py -a /path/to/actions.kbd -w actions/actions_tmux.98.kbd
"""

import argparse
import re
from pathlib import Path

DEFAULT_ACTIONS_FILE = Path.home() / ".config" / "kanata" / "actions" / "actions.kbd"

# Matches an autogen-tagged action in actions.kbd, e.g.:
#   action_lctl+a (t! unmod_all (switch ;;@autogen@
#   !action_tab_next (t! unmod_all (switch ;;@autogen@
ACTION_RE = re.compile(r"^\s*(!?action_[^\s]+).*@autogen@")

# Matches an app-prefixed action in an app file, e.g.:
#   nvim_action_tab_next  (macro esc ...)
# group(1) = app name, group(2) = action name (action_...)
APP_ACTION_RE = re.compile(r"^\s*([^\s]+)_(action_[^\s]+).*")

# Matches comment-only or blank lines.
COMMENT_OR_EMPTY_LINE_RE = re.compile(r"^\s*(;;|$)")

# Matches the opening (defvar line.
DEFVAR_RE = re.compile(r"^\s*\(defvar\b")

# Matches a closing parenthesis line.
CLOSE_PAREN_RE = re.compile(r"^\s*\)")

# Matches any variable definition line (identifier followed by whitespace).
# Excludes comments (;), open-parens, and blank lines.
VAR_DEF_RE = re.compile(r"^\s*([^\s;(][^\s]*)\s")


def get_app_from_filename(path: Path) -> str:
    """Extract the app name from an app actions filename.

    Args:
        path: Path to a file named actions_<app>[.<order>].kbd.

    Returns:
        The app name portion of the filename (e.g. "tmux", "chrome").

    Raises:
        ValueError: If the filename doesn't match the expected pattern.
    """
    m = re.match(r"actions_([^\.]+)", path.stem)
    if not m:
        raise ValueError(f"Cannot get app name from filename: {path.name}")
    return m.group(1)


def read_existing_app_file(path: Path) -> tuple[dict[str, str], list[str]]:
    """Read an existing app actions file and extract its contents.

    Separates the file into action definitions (lines matching
    <app>_action_<name>) and other variable definitions (any other
    non-comment, non-structural variable line).

    Args:
        path: Path to the app actions file.

    Returns:
        A tuple of:
          - app_actions: dict mapping action name (e.g. "action_tab_next")
            to the full line text.
          - extra_vars: list of non-action variable definition lines
            (e.g. "  tmux_prefix  A-b").
    """
    actions: dict[str, str] = {}
    extra_vars: list[str] = []
    if not path.exists():
        return actions, extra_vars

    lines = path.read_text().splitlines()
    for line in lines:
        m = APP_ACTION_RE.match(line)
        if m:
            actions[m.group(2)] = line
        elif (
            VAR_DEF_RE.match(line)
            and not DEFVAR_RE.match(line)
            and not CLOSE_PAREN_RE.match(line)
        ):
            extra_vars.append(line)

    return actions, extra_vars


def gen_app_actions(
    app: str,
    actions: list[str],
    actions_comments: dict[str, list[str]],
    app_actions: dict[str, str],
    extra_vars: list[str],
) -> list[str]:
    """Generate the full content of an app actions file.

    Produces a (defvar ...) block with three sections:
      1. App variables — non-action variables preserved from the existing file.
      2. App-specific actions — actions defined in the app file but absent
         from actions.kbd.
      3. Interface actions — all actions from actions.kbd, with existing
         implementations kept and missing ones commented out.

    Args:
        app: App name (e.g. "tmux").
        actions: Ordered list of action names from actions.kbd
            (e.g. ["action_lctl+a", "action_tab_next", ...]).
        actions_comments: Maps each action name to its preceding comment
            lines from actions.kbd.
        app_actions: Existing action implementations from the app file,
            mapping action name to full line text.
        extra_vars: Non-action variable lines to preserve.

    Returns:
        List of output lines forming the complete file content.
    """
    result = []
    result.append("(defvar")

    # Preserve non-action variables (e.g. tmux_prefix)
    if extra_vars:
        result.append("")
        result.append(
            ";; == App variables ============================================="
        )
        result.extend(extra_vars)

    # Preserve app-specific actions that don't exist in actions.kbd
    actions_set: set[str] = set(actions)
    extra_actions: list[str] = [a for a in app_actions if a not in actions_set]
    if extra_actions:
        result.append("")
        result.append(
            ";; == App-specific actions (not in actions.kbd) ================="
        )
        for action in extra_actions:
            result.append(app_actions[action])

    result.append("")
    result.append(";; == App actions in interfaces (actions.kbd) ===============")
    for action in actions:
        result.extend(actions_comments[action])
        if action in app_actions:
            result.append(app_actions[action])
        else:
            result.append(f";; {app}_{action:<30}")

    result.append(")")
    return result


def process_actions(
    actions_file: Path,
    app: str,
    app_actions: dict[str, str],
    extra_vars: list[str],
) -> list[str]:
    """Parse the shared actions.kbd and generate app-specific output.

    Reads actions.kbd to collect all @autogen@-tagged action names and
    their preceding comments, then delegates to gen_app_actions to
    produce the output.

    Args:
        actions_file: Path to the shared actions.kbd file.
        app: App name (e.g. "tmux").
        app_actions: Existing action implementations from the app file.
        extra_vars: Non-action variable lines to preserve.

    Returns:
        List of output lines forming the complete app file content.
    """
    lines = actions_file.read_text().splitlines()
    i = 0
    comments: list[str] = []
    actions_comments: dict[str, list[str]] = {}
    actions: list[str] = []
    while i < len(lines):
        while COMMENT_OR_EMPTY_LINE_RE.match(lines[i]):
            comments.append(lines[i].strip())
            i = i + 1

        m = ACTION_RE.match(lines[i])
        # Action comments must be immediately above the action, or they will be discarded.
        if not m:
            comments = []
            i = i + 1
            continue

        # action_ or !action_ are treated the same way.
        action = m.group(1).lstrip("!")
        actions.append(action)
        if action in actions_comments:
            actions_comments[action].extend(comments)
        else:
            actions_comments[action] = comments

        comments = []
        i = i + 1
    # Get rid of possible duplicates (actions & !action) but keep the order.
    actions = list(dict.fromkeys(actions))
    return gen_app_actions(app, actions, actions_comments, app_actions, extra_vars)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sync action interfaces from a shared actions.kbd into an\n"
            "app-specific actions file (e.g. actions_chrome.4.kbd).\n\n"
            "When the target file exists, existing action implementations,\n"
            "non-action variables, and app-specific actions are preserved.\n"
            "Missing actions are added as commented-out placeholders."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "actions_app_file",
        help=(
            "Output actions file (e.g. actions/actions_chrome.4.kbd).\n"
            "If the file exists it will be updated, preserving existing\n"
            "implementations. If it doesn't exist it will be created with\n"
            "all actions commented out."
        ),
    )

    parser.add_argument(
        "-w",
        "--write",
        action="store_true",
        help="Write the result to the output file. Without this flag, the result is printed to stdout.",
    )

    parser.add_argument(
        "-a",
        "--actions-file",
        type=Path,
        default=DEFAULT_ACTIONS_FILE,
        help=f"Path to the shared actions.kbd file (default: {DEFAULT_ACTIONS_FILE}).",
    )

    args = parser.parse_args()

    actions_file: Path = args.actions_file
    output_path = Path(args.actions_app_file)
    app = get_app_from_filename(output_path)

    print(f"Input actions file : {actions_file}")
    print(f"Output file        : {output_path}")
    print(f"Inferred app       : {app}")
    print(f"Mode               : {'WRITE' if args.write else 'DRY-RUN'}")

    app_actions, extra_vars = read_existing_app_file(output_path)
    result = process_actions(actions_file, app, app_actions, extra_vars)
    output = "\n".join(result)

    if args.write:
        output_path.write_text(output + "\n")
        print(f"Wrote {output_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
