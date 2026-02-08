#!/usr/bin/env python3

import argparse
import re
from collections import defaultdict
from pathlib import Path

ACTION_START_RE = re.compile(r"^\s*(action_[^\s]+)\s")
ACTION_END = ")"
VK_LINE_RE = re.compile(r"\(\(input virtual vk_(\w+)\)\)\s+(.*?)\s+break")
COMMENT_RE = re.compile(r"^\s*;;")


def split_actions(actions_file: Path):
    lines = actions_file.read_text(encoding="utf-8").splitlines()

    per_app_lines = defaultdict(list)

    current_action = None
    action_comments = []

    for line in lines:
        # --- Comments ---
        if COMMENT_RE.match(line):
            action_comments.append(line.rstrip())
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

            per_app_lines[app].append(f"  {app}_action_{short_action:<30} {combo}")

        # --- End of action block ---
        if line.strip().startswith(ACTION_END):
            current_action = None
            action_comments = []

    return per_app_lines


def write_files(per_app_lines, output_dir: Path):
    for app, lines in per_app_lines.items():
        path = output_dir / f"actions_{app}.kbd"
        lines = ["(defvar", *lines, ")"]
        content = "\n".join(lines).rstrip() + "\n"
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path}")


def confirm(actions_file: Path, output_dir: Path, apps):
    print("\n🔧 Sync actions")
    print(f"  Input file : {actions_file.resolve()}")
    print(f"  Output dir : {output_dir.resolve()}")
    print("  Files to generate:")
    for app in sorted(apps):
        print(f"    - actions_{app}.kbd")

    answer = input("\nContinue? [y/N]: ").strip().lower()
    return answer == "y"


def main():
    parser = argparse.ArgumentParser(
        description="Split actions.kbd into per-application action files."
    )
    parser.add_argument(
        "actions_file",
        nargs="?",
        default="actions.kbd",
        help="Input actions file (default: ./actions.kbd)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=".",
        help="Directory to write actions_<app>.kbd files (default: .)",
    )

    args = parser.parse_args()

    actions_file = Path(args.actions_file)
    output_dir = Path(args.output_dir)

    if not actions_file.exists():
        parser.error(f"Input file not found: {actions_file}")

    output_dir.mkdir(parents=True, exist_ok=True)

    per_app_lines = split_actions(actions_file)

    if not per_app_lines:
        print("No application-specific actions found. Nothing to do.")
        return

    if not confirm(actions_file, output_dir, per_app_lines.keys()):
        print("Aborted.")
        return

    write_files(per_app_lines, output_dir)


if __name__ == "__main__":
    main()
