#!/usr/bin/env python3

import re
from collections import defaultdict
from pathlib import Path

ACTIONS_FILE = Path("actions.kbd")

ACTION_START_RE = re.compile(r"^\s*(action_[^\s]+)\b")
ACTION_END = ")"
VK_LINE_RE = re.compile(r"\(\(input virtual vk_(\w+)\)\)\s+(.*?)\s+break")
COMMENT_RE = re.compile(r"^\s*;;")


def split_actions():
    lines = ACTIONS_FILE.read_text().splitlines()

    per_app_lines = defaultdict(list)

    current_action = None
    action_comments = []

    for line in lines:
        # --- Comments ---
        if COMMENT_RE.match(line):
            action_comments.append(line.strip())
            continue

        # --- Start of an action ---
        m_action = ACTION_START_RE.match(line)
        if m_action:
            current_action = m_action.group(1)  # action_lctl+b
            continue

        # --- vk_<app> lines ---
        m_vk = VK_LINE_RE.search(line)
        if m_vk and current_action:
            app = m_vk.group(1)
            combo = m_vk.group(2).strip()
            short_action = current_action[len("action_") :]

            # Copy comments for THIS action into THIS app
            if action_comments:
                per_app_lines[app].extend(action_comments)

            per_app_lines[app].append(f"{app}_action_{short_action:<30} {combo}")
        # --- End of action block ---
        if line.strip().startswith(ACTION_END):
            current_action = None
            action_comments = []

    return per_app_lines


def write_files(per_app_lines):
    for app, lines in per_app_lines.items():
        path = Path(f"__actions_{app}.kbd")
        lines.insert(0, "(defvar")
        lines.append(")")
        content = "\n".join(lines).rstrip() + "\n"
        path.write_text(content)
        print(f"Wrote {path}")


def main():
    per_app_lines = split_actions()
    write_files(per_app_lines)


if __name__ == "__main__":
    main()
