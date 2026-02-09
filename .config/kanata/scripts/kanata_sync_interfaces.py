#!/usr/bin/env python3

import argparse
import re
from pathlib import Path

ACTIONS_FILE = Path.home() / ".config" / "kanata" / "actions" / "actions.kbd"

ACTION_RE = re.compile(r"^\s*(!?action_[^\s]+).*@autogen@")
APP_ACTION_RE = re.compile(r"^\s*([^\s]+)_(action_[^\s]+).*")
COMMENT_OR_EMPTY_LINE_RE = re.compile(r"^\s*(;;|$)")


def get_app_from_filename(path: Path) -> str:
    """
    Extract app name from actions_<app>.*.kbd
    """
    m = re.match(r"actions_([^\.]+)", path.stem)
    if not m:
        raise ValueError(f"Cannot get app name from filename: {path.name}")
    return m.group(1)


def read_existing_app_actions(path: Path) -> dict[str, str]:
    """ """
    actions = {}
    if path.exists():
        lines = path.read_text().splitlines()
        for line in lines:
            # For any <app>_<action_name> save line for key <action_name>
            m = APP_ACTION_RE.match(line)
            if m:
                actions[m.group(2)] = line
    return actions


def gen_app_actions(
    app: str,
    actions: list[str],
    actions_comments: dict[str, list[str]],
    app_actions: dict[str, str],
) -> list[str]:
    result = []
    result.append("(defvar")
    for action in actions:
        result.extend(actions_comments[action])
        if action in app_actions:
            result.append(app_actions[action])
        else:
            result.append(f";; {app}_{action:<30}")
    result.append(")")
    return result


def process_actions(app: str, app_actions: dict[str, str]) -> list[str]:

    lines = ACTIONS_FILE.read_text().splitlines()
    i = 0
    comments = []
    actions_comments = {}
    actions = []
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

        i = i + 1
    # Get rid of possible duplicates (actions & !action) but keep the order.
    actions = list(dict.fromkeys(actions))
    return gen_app_actions(app, actions, actions_comments, app_actions)


def main():
    parser = argparse.ArgumentParser(
        description=f"Sync actions from {ACTIONS_FILE} into an app-specific actions file."
    )

    parser.add_argument(
        "actions_app_file",
        help="""
          Output actions file (e.g. actions_chrome.kbd). If file exists the file
          will be modified, adding non existing actions from actions.kbd and keeping
          already existing ones. If file doesn't exist it will be created and
          all actions from actions.kbd will be added.
          """,
    )

    parser.add_argument(
        "-w",
        "--write",
        action="store_true",
        help="Write the result to the output file. Without this flag, the result is printed to stdout.",
    )

    args = parser.parse_args()

    output_path = Path(args.actions_app_file)
    app = get_app_from_filename(output_path)

    print(f"Input actions file : {ACTIONS_FILE}")
    print(f"Output file        : {output_path}")
    print(f"Inferred app       : {app}")
    print(f"Mode               : {'WRITE' if args.write else 'DRY-RUN'}")

    app_actions = read_existing_app_actions(output_path)
    result = process_actions(app, app_actions)
    output = "\n".join(result)

    if args.write:
        output_path.write_text(output + "\n")
        print(f"Wrote {output_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
