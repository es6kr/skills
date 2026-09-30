#!/usr/bin/env python3
"""
update_marker.py - Update an item's status marker in fix_plan.md / checklist.md.

Only the "- [...]" marker segment at the start of the matched line is
replaced; everything after the marker (including any bracketed text such as
a "Plane [KEY-N]" reference) is preserved verbatim. --query is used solely to
locate the target line and must match exactly one line.

Usage:
  python update_marker.py --file <path> --query <pattern> --prefix <new-marker> [--dry-run]
"""

import re
import sys
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

MARKER_RE = re.compile(r"^- \[[^\]]*\]")


def parse_args():
    parser = argparse.ArgumentParser(description="Update task marker in fix_plan.md")
    parser.add_argument("--file", required=True, help="Path to fix_plan.md")
    parser.add_argument("--query", required=True, help="Query substring to identify the task item (must match exactly one line)")
    parser.add_argument(
        "--prefix",
        "--replacement-prefix",
        dest="prefix",
        required=True,
        help="New marker only, e.g. '- [x]' or '- [BLOCKED:P2:selfable]' -- everything after the old marker is kept unchanged",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the change without writing the file")
    return parser.parse_args()


def update_marker(file_path, query, prefix, dry_run=False):
    path = Path(file_path)
    if not path.exists():
        print(f"Error: {file_path} does not exist.")
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    matches = [i for i, line in enumerate(lines) if line.startswith("- [") and query in line]

    if len(matches) == 0:
        print(f"Error: No task item matching '{query}' found in {file_path}.")
        sys.exit(1)
    if len(matches) > 1:
        line_numbers = [m + 1 for m in matches]
        print(f"Error: Query '{query}' matches {len(matches)} lines (must match exactly one). Line numbers: {line_numbers}")
        sys.exit(1)

    matched_idx = matches[0]
    old_line = lines[matched_idx]

    marker_match = MARKER_RE.match(old_line)
    if not marker_match:
        print(f"Error: line {matched_idx + 1} does not start with a recognizable '- [...]' marker:\n  {old_line.strip()}")
        sys.exit(1)

    rest = old_line[marker_match.end():]
    sub_line = f"{prefix.strip()}{rest}"

    if dry_run:
        print(f"[dry-run] Would update line {matched_idx + 1}:\n  Old: {old_line.strip()}\n  New: {sub_line.strip()}")
        return

    lines[matched_idx] = sub_line
    path.write_text("".join(lines), encoding="utf-8")
    print(f"Updated line {matched_idx + 1}:\n  Old: {old_line.strip()}\n  New: {sub_line.strip()}")


if __name__ == "__main__":
    args = parse_args()
    update_marker(args.file, args.query, args.prefix, dry_run=args.dry_run)
