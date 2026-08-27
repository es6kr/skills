#!/usr/bin/env python3
"""
update_marker.py - Update an item's status marker in fix_plan.md / checklist.md.

Usage:
  python update_marker.py --file <path> --query <pattern> --replacement-prefix <prefix>
"""

import re
import sys
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Update task marker in fix_plan.md")
    parser.add_argument("--file", required=True, help="Path to fix_plan.md")
    parser.add_argument("--query", required=True, help="Query substring to identify the task item")
    parser.add_argument("--prefix", required=True, help="Complete prefix to replace up to the main title text")
    return parser.parse_args()


def update_marker(file_path, query, prefix):
    path = Path(file_path)
    if not path.exists():
        print(f"Error: {file_path} does not exist.")
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    matched_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("- [") and query in line:
            matched_idx = i
            break

    if matched_idx == -1:
        print(f"Error: No task item matching '{query}' found in {file_path}.")
        sys.exit(1)

    old_line = lines[matched_idx]
    # Keep query and rest of line after query match
    # Find where query begins
    q_pos = old_line.find(query)
    rest = old_line[q_pos:]
    sub_line = f"{prefix.strip()} {rest}"

    lines[matched_idx] = sub_line
    path.write_text("".join(lines), encoding="utf-8")
    print(f"Updated line {matched_idx+1}:\n  Old: {old_line.strip()}\n  New: {sub_line.strip()}")


if __name__ == "__main__":
    args = parse_args()
    update_marker(args.file, args.query, args.prefix)
