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

BACKTICK STRING CONVERSION:
  Actions can be defined using a simplified backtick syntax which gets
  automatically converted to kanata macro syntax. Example:

    tmux_action_new_window  `:w FILE{ent}`

  Gets converted to:

    ;; tmux_action_new_window  `:w FILE{ent}`
    tmux_action_new_window  (macro S-; w spc S-f S-i S-l S-e ent)

  Conversion rules (US keyboard):
    - Uppercase letters → S-<lowercase> (e.g., "A" → "S-a")
    - Shifted symbols → S-<base> (e.g., ":" → "S-;", "!" → "S-1")
    - Spaces → spc
    - Special keywords in {} → keyword (e.g., "{ent}" → "ent")
    - Lowercase letters and non-shifted symbols → as-is

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
#   ~action_tab_next (t! unmod_all (switch ;;@autogen@
ACTION_RE = re.compile(r"^\s*(~?action_[^\s]+).*@autogen@")

ACTIONS_START_RE = re.compile(r"^\s*;;\s*@start@")

# Matches an app-prefixed action in an app file, e.g.:
#   nvim_action_tab_next  (macro esc ...)
# group(1) = app name, group(2) = action name (action_...)
APP_ACTION_RE = re.compile(r"^\s*([^\s]+)_(action_[^\s]+).*")

# Matches action with backtick string, e.g.:
#   nvim_action_foo  `:w FILE{ent}`
# group(1) = whitespace, group(2) = app, group(3) = action name, group(4) = backtick content
BACKTICK_ACTION_RE = re.compile(r"^(\s*)([^\s]+)_(action_[^\s]+)\s+`([^`]+)`\s*$")

# Matches blank-lines lines.
EMPTY_LINE_RE = re.compile(r"^\s*$")
# Matches comment-only lines.
COMMENT_LINE_RE = re.compile(r"^\s*;;")

# Matches the opening (defvar line.
DEFVAR_RE = re.compile(r"^\s*\(defvar\b")

# Matches a closing parenthesis line.
CLOSE_PAREN_RE = re.compile(r"^\s*\)")

# Matches any variable definition line (identifier followed by whitespace).
# Excludes comments (;), open-parens, and blank lines.
VAR_DEF_RE = re.compile(r"^\s*([^\s;(][^\s]*)\s")

REVERSE_ACTION_FLAG = "~"

# US Keyboard shift mappings for symbols
SHIFT_MAP = {
    "!": "S-1",
    "@": "S-2",
    "#": "S-3",
    "$": "S-4",
    "%": "S-5",
    "^": "S-6",
    "&": "S-7",
    "*": "S-8",
    "(": "S-9",
    ")": "S-0",
    "_": "S--",
    "+": "S-=",
    "{": "S-[",
    "}": "S-]",
    "|": "S-\\",
    ":": "S-;",
    '"': "S-'",
    "<": "S-,",
    ">": "S-.",
    "?": "S-/",
    "~": "S-grv",
}


def convert_backtick_to_macro(backtick_content: str) -> str:
    """Convert backtick string to kanata macro syntax.

    Processes a string enclosed in backticks and converts it to kanata's
    macro format with proper key codes.

    Rules:
      - Uppercase letters → S-<lowercase> (e.g., "A" → "S-a")
      - Shifted symbols → S-<base_key> (e.g., ":" → "S-;")
      - Spaces → spc
      - Special keywords in curly braces → keyword (e.g., "{ent}" → "ent")
      - Lowercase letters and non-shifted symbols → as-is

    Args:
        backtick_content: String content from within backticks.

    Returns:
        Space-separated string of kanata macro key codes.

    Examples:
        >>> convert_backtick_to_macro(":w FILE{ent}")
        'S-; w spc S-f S-i S-l S-e ent'
        >>> convert_backtick_to_macro("hello world")
        'h e l l o spc w o r l d'
    """
    result = []
    i = 0
    while i < len(backtick_content):
        char = backtick_content[i]

        # Handle special keywords in curly braces like {ent}, {tab}, {bspc}
        if char == "{":
            j = backtick_content.find("}", i)
            if j != -1:
                keyword = backtick_content[i + 1 : j]
                result.append(keyword)
                i = j + 1
                continue

        # Handle space
        if char == " ":
            result.append("spc")
        # Handle uppercase letters
        elif char.isupper():
            result.append(f"S-{char.lower()}")
        # Handle shifted symbols
        elif char in SHIFT_MAP:
            result.append(SHIFT_MAP[char])
        # Handle lowercase letters and non-shifted symbols
        elif char.islower() or char in "-=[];',.`/\\":
            # Map backtick to grv
            if char == "`":
                result.append("grv")
            else:
                result.append(char)
        else:
            # For any other character, keep as-is (fallback)
            result.append(char)

        i += 1

    return " ".join(result)


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


def read_existing_app_file(
    path: Path,
) -> tuple[dict[str, tuple[list[str], str]], list[str]]:
    """Read an existing app actions file and extract its contents.

    Separates the file into action definitions (with their preceding comments)
    and other variable definitions.

    When an action line contains a backtick string (e.g., action  `string`),
    it converts the backtick string to kanata macro syntax.

    Args:
        path: Path to the app actions file.

    Returns:
        A tuple of:
          - app_actions: dict mapping action name (e.g. "action_tab_next")
            to a tuple of (comments_list, implementation_line).
          - extra_vars: list of non-action variable definition lines
            (e.g. "  tmux_prefix  A-b").
    """
    actions: dict[str, tuple[list[str], str]] = {}
    extra_vars: list[str] = []
    if not path.exists():
        return actions, extra_vars

    lines = path.read_text().splitlines()
    pending_comments: list[str] = []

    for line in lines:
        # Collect comments and blank lines
        if EMPTY_LINE_RE.match(line):
            pending_comments = []
            continue
        if COMMENT_LINE_RE.match(line):
            pending_comments.append(line.strip())
            continue

        # Check for backtick action (must come before APP_ACTION_RE since it's more specific)
        backtick_match = BACKTICK_ACTION_RE.match(line)
        if backtick_match:
            whitespace = backtick_match.group(1)
            app = backtick_match.group(2)
            action_name = backtick_match.group(3)
            backtick_content = backtick_match.group(4)

            # Convert backtick string to macro
            macro_content = convert_backtick_to_macro(backtick_content)

            # Store backtick comment + implementation
            backtick_comment = (
                f"{whitespace};; {app}_{action_name}  `{backtick_content}`"
            )
            implementation = f"{whitespace}{app}_{action_name}  (macro {macro_content})"

            # Add backtick comment to pending comments
            comments_with_backtick = pending_comments + [backtick_comment]
            actions[action_name] = (comments_with_backtick, implementation)
            pending_comments = []
            continue

        # Check for regular app action
        m = APP_ACTION_RE.match(line)
        if m:
            actions[m.group(2)] = (pending_comments, line)
            pending_comments = []
            continue

        # Check for non-action variables
        if (
            VAR_DEF_RE.match(line)
            and not DEFVAR_RE.match(line)
            and not CLOSE_PAREN_RE.match(line)
        ):
            extra_vars.append(line)
            pending_comments = []

    return actions, extra_vars


def merge_comments(official_comments: list[str], app_comments: list[str]) -> list[str]:
    """Merge official comments from actions.kbd with user-added comments from app file.

    Args:
        official_comments: Comments from actions.kbd for this action.
        app_comments: Comments from app file for this action.

    Returns:
        Merged list: official comments + user-specific comments (not in official).
    """
    # Find comments that are in app file but NOT in official comments
    official_set = set(official_comments)
    user_comments = [c for c in app_comments if c not in official_set]

    # Return: official comments + user-added comments
    return official_comments + user_comments


def gen_app_actions(
    app: str,
    actions: list[str],
    actions_comments: dict[str, list[str]],
    app_actions: dict[str, tuple[list[str], str]],
    extra_vars: list[str],
) -> list[str]:
    """Generate the full content of an app actions file.

    Produces a (defvar ...) block with three sections:
      1. App variables — non-action variables preserved from the existing file.
      2. App-specific actions — actions defined in the app file but absent
         from actions.kbd.
      3. Interface actions — all actions from actions.kbd, with existing
         implementations kept and missing ones commented out.

    Comments are intelligently merged:
      - Official comments from actions.kbd are always included
      - User-added comments from app file (not in actions.kbd) are preserved

    Args:
        app: App name (e.g. "tmux").
        actions: Ordered list of action names from actions.kbd
            (e.g. ["action_lctl+a", "action_tab_next", ...]).
        actions_comments: Maps each action name to its preceding comment
            lines from actions.kbd.
        app_actions: Existing action implementations from the app file,
            mapping action name to tuple of (comments_list, implementation_line).
        extra_vars: Non-action variable lines to preserve.

    Returns:
        List of output lines forming the complete file content.
    """
    result = []
    result.append("(defvar")

    # Preserve non-action variables (e.g. tmux_prefix)
    if extra_vars:
        # result.append("")
        # result.append(
        #     ";; == App variables ============================================="
        # )
        result.extend(extra_vars)

    # Preserve app-specific actions that don't exist in actions.kbd
    actions_set: set[str] = set(actions)
    extra_actions: list[str] = [a for a in app_actions if a not in actions_set]
    if extra_actions:
        # result.append("")
        # result.append(
        #     ";; == App-specific actions (not in actions.kbd) ================="
        # )
        for action in extra_actions:
            app_comments, app_implementation = app_actions[action]
            result.extend(app_comments)
            result.append(app_implementation)

    # result.append("")
    # result.append(";; == App actions in interfaces (actions.kbd) ===============")
    for action in actions:
        official_comments = actions_comments[action]

        if action in app_actions:
            app_comments, app_implementation = app_actions[action]

            # Merge: official comments + user-specific comments
            merged_comments = merge_comments(official_comments, app_comments)
            result.extend(merged_comments)
            result.append(app_implementation)
        else:
            # Not implemented - show official comments and placeholder
            result.extend(official_comments)
            result.append(f";; {app}_{action:<30}")

    result.append(")")
    return result


def process_actions(
    actions_file: Path,
    app: str,
    app_actions: dict[str, tuple[list[str], str]],
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
    # Remove top actions.kbd comments that are not replicated in actions_<app>.kbd
    while i < len(lines):
        if ACTIONS_START_RE.match(lines[i]):
            i = i + 1
            break
        i = i + 1

    while i < len(lines):
        while COMMENT_LINE_RE.match(lines[i]) or EMPTY_LINE_RE.match(lines[i]):
            comments.append(lines[i].strip())
            i = i + 1

        m = ACTION_RE.match(lines[i])
        # Action comments must be immediately above the action, or they will be discarded.
        if not m:
            comments = []
            i = i + 1
            continue

        # action_ or ~action_ are treated the same way.
        action = m.group(1).lstrip(REVERSE_ACTION_FLAG)
        actions.append(action)
        if action in actions_comments:
            actions_comments[action].extend(comments)
        else:
            actions_comments[action] = comments

        comments = []
        i = i + 1
    # Get rid of possible duplicates (actions & ~action) but keep the order.
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
