#!/usr/bin/env python3
"""
Sync action interfaces from a shared actions_*.iface.kbd file into a per-app
action file (e.g. actions/chrome/chrome_omni.kbd).

When the target file already exists, the script preserves:
  - Existing action implementations (uncommented action lines).
  - Non-action variable definitions and their preceding comments
    (e.g. tmux_prefix).
  - App-specific actions not present in the shared file.
Actions that exist in the shared file but are missing from the app file
are added as commented-out placeholders.

BACKTICK STRING CONVERSION:
  Actions can be defined using a simplified backtick syntax which gets
  automatically converted to kanata macro syntax. Example:

    tmux_action_new_window  `:w FILE{ent}`

  Gets converted to:

    ;; tmux_action_new_window  `:w FILE{ent}`
    tmux_action_new_window  (macro S-; w spc S-f S-i S-l S-e ent)

  Conversion rules (US keyboard):
    - Kanata variables ($name) → included as-is (e.g., "$tmux_prefix")
    - Uppercase letters → S-<lowercase> (e.g., "A" → "S-a")
    - Shifted symbols → S-<base> (e.g., ":" → "S-;", "!" → "S-1")
    - Digits → Digit# (e.g., "5" → "Digit5")
    - Spaces → spc (except around variables, where they are separators)
    - Special keywords in {} → keyword (e.g., "{ent}" → "ent")
    - Lowercase letters and non-shifted symbols → as-is

Usage:
  # Dry-run (prints to stdout):
  ./kanata_sync_interfaces.py actions/tmux/tmux_panes.19.kbd

  # Write changes to the file:
  ./kanata_sync_interfaces.py -w actions/tmux/tmux_panes.19.kbd

  # Use a custom shared action file:
  ./kanata_sync_interfaces.py -a /path/to/actions_panes.iface.kbd -w actions/tmux/tmux_panes.19.kbd
"""

import argparse
import re
from pathlib import Path

DEFAULT_ACTIONS_FOLDER = Path.home() / ".config" / "kanata" / "actions"

# Matches an @iface@-tagged action in actions.kbd, e.g.:
#   action_lctl+a (t! unmod_all (switch ;;@iface@
#   ~action_tab_next (t! unmod_all (switch ;;@iface@
ACTION_RE = re.compile(r"^\s*(~?action_[^\s]+).*@iface@")

ACTIONS_START_RE = re.compile(r"^\s*;;\s*@start@")

# Matches an app-prefixed action in an app file, e.g.:
#   nvim_action_tab_next  (macro esc ...)
# group(1) = app name, group(2) = action name (action_...)
APP_ACTION_RE = re.compile(r"^\s*([^\s]+)_(action_[^\s]+).*")

# Matches action with backtick string, e.g.:
#   nvim_action_foo  `:w FILE{ent}`
# group(1) = whitespace, group(2) = text, group(3) = backtick expression
BACKTICK_EXPRESSION_RE = re.compile(r"^(\s*)([^\s]+)(\s+)`([^`]+)`\s*$")

# Matches blank lines.
EMPTY_LINE_RE = re.compile(r"^\s*$")
# Matches comment-only lines.
COMMENT_LINE_RE = re.compile(r"^\s*;;")

# Matches the opening (defvar line.
DEFVAR_RE = re.compile(r"^\s*\(defvar\b")

# Matches a closing parenthesis line.
CLOSE_PAREN_RE = re.compile(r"^\s*\)")

# Matches any variable definition line (identifier followed by whitespace).
# Excludes comments (;), open-parens, and blank lines.
VAR_RE = re.compile(r"^\s*([^\s;(][^\s]*)\s")

IFACE_PRIORITY_RE = re.compile(r"^(\w+)(?:\.\d+)?$")

REVERSE_ACTION_FLAG = "~"

TO_SET_PREFIX = "___TO_SET___"
TO_SET_PREFIX_RE = re.compile(r".*___TO_SET___.*")

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


def _char_to_keycode(char: str) -> str:
    """Convert a single character to its kanata key code."""
    if char == " ":
        return "spc"
    if char.isdigit():
        return f"Digit{char}"
    if char.isupper():
        return f"S-{char.lower()}"
    if char in SHIFT_MAP:
        return SHIFT_MAP[char]
    if char == "`":
        return "grv"
    return char


def convert_backtick_to_macro(backtick_content: str) -> str:
    """Convert backtick string to kanata macro syntax.

    Processes a string enclosed in backticks and converts it to kanata's
    macro format with proper key codes.

    Rules:
      - Kanata variables ($name) → included as-is (e.g., "$my_var")
      - Spaces adjacent to variables → separators (not keystrokes)
      - Uppercase letters → S-<lowercase> (e.g., "A" → "S-a")
      - Shifted symbols → S-<base_key> (e.g., ":" → "S-;")
      - Digits → Digit# (e.g., "5" → "Digit5")
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
        >>> convert_backtick_to_macro("$my_var ssVG")
        '$my_var s s S-v S-g'
        >>> convert_backtick_to_macro("$tmux_prefix c")
        '$tmux_prefix c'
        >>> convert_backtick_to_macro("hello world")
        'h e l l o spc w o r l d'
    """
    result = []
    i = 0
    while i < len(backtick_content):
        char = backtick_content[i]

        # Handle kanata variables ($name) — included as-is in macro.
        # Spaces around variables are separators, not keystrokes.
        if char == "$":
            j = i + 1
            while j < len(backtick_content) and backtick_content[j] not in " {":
                j += 1
            result.append(backtick_content[i:j])
            # Skip trailing spaces (separators)
            while j < len(backtick_content) and backtick_content[j] == " ":
                j += 1
            i = j
            continue

        # Handle spaces: spc unless they precede a variable (separator)
        if char == " ":
            j = i
            while j < len(backtick_content) and backtick_content[j] == " ":
                j += 1
            if j < len(backtick_content) and backtick_content[j] == "$":
                i = j
                continue
            result.append("spc")
            i += 1
            continue

        # Handle special keywords in curly braces like {ent}, {tab}, {bspc}
        if char == "{":
            j = backtick_content.find("}", i)
            if j != -1:
                keyword = backtick_content[i + 1 : j]
                result.append(keyword if keyword != "{" else _char_to_keycode("{"))
                i = j + 1
                continue

        result.append(_char_to_keycode(char))
        i += 1

    return " ".join(result)


def get_app_and_interface_from_filename(path: Path) -> tuple[str, str]:
    """Extract app name and interface name from a per-app action filename.

    Uses the parent directory name as the app name and strips the <app>_
    prefix from the filename stem to get the interface name.

    Args:
        path: Path to a file named <app>_<name>[.<priority>].kbd inside
              an <app>/ subdirectory.

    Returns:
        Tuple of (app_name, interface_name).

    Raises:
        ValueError: If the filename doesn't match the expected pattern.
    """
    app_name = path.parent.name
    prefix = f"{app_name}_"
    stem = path.stem
    if not stem.startswith(prefix):
        raise ValueError(
            f"Filename {path.name} does not start with expected prefix '{prefix}'"
        )
    remainder = stem[len(prefix) :]
    m = re.match(IFACE_PRIORITY_RE, remainder)
    if not m:
        raise ValueError(f"Cannot parse per-app action filename: {path.name}")
    return app_name, m.group(1)


def _count_parens(text: str) -> tuple[int, int]:
    """Count opening and closing parentheses in a string.

    Args:
        text: String to analyze.

    Returns:
        Tuple of (opening_count, closing_count).
    """
    opening = text.count("(")
    closing = text.count(")")
    return opening, closing


def _read_multiline_expression(
    lines: list[str], start_index: int, initial_line: str
) -> tuple[str, int]:
    """Read a potentially multi-line lisp expression.

    If the initial_line has unmatched opening parentheses, continues
    reading subsequent lines until all parentheses are balanced.

    Args:
        lines: List of all lines in the file
        start_index: Index of the initial line
        initial_line: The first line of the expression

    Returns:
        Tuple of:
          - complete_expression: The full expression (may span multiple lines)
          - last_index: Index of the last line consumed
    """
    expression = initial_line

    # Check if expression spans multiple lines by counting parentheses
    opening, closing = _count_parens(initial_line)
    paren_balance = opening - closing

    # If there are unmatched opening parentheses, read subsequent lines
    if paren_balance > 0:
        j = start_index + 1
        while j < len(lines) and paren_balance > 0:
            next_line = lines[j]
            expression += "\n" + next_line
            opening, closing = _count_parens(next_line)
            paren_balance += opening - closing
            j += 1
        return expression, j - 1  # Return last line consumed

    return expression, start_index  # Single-line expression


def read_existing_app_file(
    path: Path,
) -> tuple[list[str], dict[str, tuple[list[str], str]], list[tuple[list[str], str]]]:
    """Read an existing app actions file and extract its contents.

    Separates the file into prelude (content before defvar), action definitions
    (with their preceding comments), and other variable definitions.

    When an action line contains a backtick string (e.g., action  `string`),
    it converts the backtick string to kanata macro syntax.

    Multi-line expressions are supported: if the action or variable body starts
    with '(' but doesn't have a matching ')' on the same line, subsequent lines
    are read until the parentheses are balanced.

    Args:
        path: Path to the app actions file.

    Returns:
        A tuple of:
          - prelude: list of lines that appear before (defvar
          - app_actions: dict mapping action name (e.g. "action_tab_next")
            to a tuple of (comments_list, implementation_line).
          - extra_vars: list of tuples (comments_list, var_line) for
            non-action variable definitions (e.g. tmux_prefix  A-b).
            Empty lines reset pending comments (they are not accumulated).
    """
    prelude: list[str] = []
    actions: dict[str, tuple[list[str], str]] = {}
    extra_vars: list[tuple[list[str], str]] = []
    if not path.exists():
        return prelude, actions, extra_vars

    lines = path.read_text().splitlines()
    pending_comments: list[str] = []
    i = 0

    # Capture everything before (defvar as prelude
    while i < len(lines):
        if DEFVAR_RE.match(lines[i]):
            i += 1
            break
        prelude.append(lines[i])
        i += 1

    while i < len(lines):
        line = lines[i]
        # Discard empty lines.
        if EMPTY_LINE_RE.match(line):
            pending_comments = []
            i += 1
            continue
        # Save comments for next action/variable. If comment is a TO_SET comment
        # discard it.
        if COMMENT_LINE_RE.match(line):
            if TO_SET_PREFIX_RE.match(line):
                pending_comments = []
            else:
                pending_comments.append(line.strip())
            i += 1
            continue

        # Check for backtick expression.
        backtick_match = BACKTICK_EXPRESSION_RE.match(line)
        if backtick_match:
            whitespace1 = backtick_match.group(1)
            text = backtick_match.group(2)
            whitespace2 = backtick_match.group(3)
            backtick_content = backtick_match.group(4)

            # Store backtick comment + implementation
            backtick_comment = (
                f"{whitespace1};; {text}{whitespace2}`{backtick_content}`"
            )
            pending_comments.append(backtick_comment)

            # Convert backtick string to macro
            macro_content = convert_backtick_to_macro(backtick_content)
            line = f"{whitespace1}{text}{whitespace2}(macro {macro_content})"

        # Check for regular app action
        m = APP_ACTION_RE.match(line)
        if m:
            action_name = m.group(2)
            action_body, last_index = _read_multiline_expression(lines, i, line)

            actions[action_name] = (pending_comments, action_body)
            pending_comments = []
            i = last_index + 1
            continue

        # Check for non-action variables
        if (
            VAR_RE.match(line)
            and not DEFVAR_RE.match(line)
            and not CLOSE_PAREN_RE.match(line)
        ):
            var_body, last_index = _read_multiline_expression(lines, i, line)

            extra_vars.append((pending_comments, var_body))
            pending_comments = []
            i = last_index + 1
            continue

        i += 1

    return prelude, actions, extra_vars


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
    extra_vars: list[tuple[list[str], str]],
    prelude: list[str],
) -> list[str]:
    """Generate the full content of an app actions file.

    Produces output with:
      0. Prelude — any code that appeared before (defvar in the original file
      1. (defvar block with:
         a. App variables — non-action variables (with their comments)
            preserved from the existing file.
         b. App-specific actions — actions defined in the app file but absent
            from actions.kbd (with their comments).
         c. Interface actions — all actions from actions.kbd, with existing
            implementations kept and missing ones as commented-out placeholders
            (prefixed with ___TO_SET___).

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
        extra_vars: List of tuples (comments_list, var_line) for non-action
            variables to preserve.
        prelude: List of lines that appear before (defvar in the original file.

    Returns:
        List of output lines forming the complete file content.
    """
    result = []

    # Add prelude (content before defvar) if it exists
    if prelude:
        result.extend(prelude)

    result.append("(defvar")

    # Preserve non-action variables (e.g. tmux_prefix)
    if extra_vars:
        # result.append("")
        # result.append(
        #     ";; == App variables ============================================="
        # )
        for var_comments, var in extra_vars:
            result.extend(var_comments)
            result.append(var)

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
            result.append(f";; {TO_SET_PREFIX} {app}_{action:<30}")

    result.append(")")
    return result


def process_actions(
    interface_file: Path,
    app: str,
    app_actions: dict[str, tuple[list[str], str]],
    extra_vars: list[tuple[list[str], str]],
    prelude: list[str],
) -> list[str]:
    """Parse an interface file and generate app-specific output.

    Reads the interface file, skips everything before the @start@ marker,
    then collects all @iface@-tagged action names and their preceding
    comments. Delegates to gen_app_actions to produce the output.

    Args:
        interface_file: Path to the interface_*.kbd file.
        app: App name (e.g. "tmux").
        app_actions: Existing action implementations from the app file.
        extra_vars: List of tuples (comments_list, var_line) for non-action
            variables to preserve.
        prelude: List of lines that appear before (defvar in the original file.

    Returns:
        List of output lines forming the complete app file content.
    """
    lines = interface_file.read_text().splitlines()
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
        if COMMENT_LINE_RE.match(lines[i]) or EMPTY_LINE_RE.match(lines[i]):
            comments.append(lines[i].strip())
            i = i + 1
            continue

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
    return gen_app_actions(
        app, actions, actions_comments, app_actions, extra_vars, prelude
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sync action interfaces from a shared actions_*.iface.kbd file into a\n"
            "per-app action file (e.g. actions/chrome/chrome_omni.kbd).\n\n"
            "When the target file exists, existing action implementations,\n"
            "non-action variables, and app-specific actions are preserved.\n"
            "Missing actions are added as commented-out placeholders."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "app_interface_file",
        help=(
            "Output per-app action file (e.g. actions/chrome/chrome_omni.kbd).\n"
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
        default=None,
        help="Path to the shared actions_*.iface.kbd file (default: auto-inferred from filename).",
    )

    args = parser.parse_args()

    output_path = Path(args.app_interface_file)
    app, interface_name = get_app_and_interface_from_filename(output_path)

    # Auto-infer the interface file from the app filename
    if args.actions_file:
        interface_file: Path = args.actions_file
    else:
        interface_file = output_path.parent.parent / f"actions_{interface_name}.iface.kbd"

    print(f"Shared action file : {interface_file}")
    print(f"Output file        : {output_path}")
    print(f"Inferred app       : {app}")
    print(f"Inferred interface : {interface_name}")
    print(f"Mode               : {'WRITE' if args.write else 'DRY-RUN'}")

    prelude, app_actions, extra_vars = read_existing_app_file(output_path)
    result = process_actions(interface_file, app, app_actions, extra_vars, prelude)
    output = "\n".join(result)

    if args.write:
        new_content = output + "\n"
        if output_path.exists() and output_path.read_text() == new_content:
            print(f"No changes: {output_path}")
        else:
            output_path.write_text(new_content)
            print(f"Wrote {output_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
