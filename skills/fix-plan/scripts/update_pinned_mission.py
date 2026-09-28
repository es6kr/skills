#!/usr/bin/env python3
"""update_pinned_mission.py — update pinned missions block in fix_plan.md / checklist.md.

Allows updating the pinned header block (before ##) safely via CLI command:
- graduate mission (mark completed or replace with current priorities)
- add/update missions and explanatory note
- uses atomic_write with UTF-8
- exit 0 on success
"""

import argparse
import io
import os
import re
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def atomic_write(path: str, text: str, prefix: str = ".update_pinned.") -> None:
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=prefix, suffix=".tmp")
    try:
        with io.open(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def update_pinned_block(text: str, graduate: list[str], add_missions: list[str], new_note: str | None) -> str:
    lines = text.split("\n")
    pinned_start = -1
    pinned_end = -1
    for i, line in enumerate(lines):
        if line.startswith("> 📌") or line.startswith("> **세션 운영 지시"):
            pinned_start = i
            break
    if pinned_start == -1:
        raise ValueError("pinned block not found in file")

    for i in range(pinned_start, len(lines)):
        if lines[i].startswith("## "):
            pinned_end = i
            break
        if not lines[i].startswith(">") and lines[i].strip():
            pinned_end = i
            break
    if pinned_end == -1:
        pinned_end = len(lines)

    pinned_lines = lines[pinned_start:pinned_end]
    new_pinned = []

    for ln in pinned_lines:
        should_skip = False
        for g in graduate:
            if g and g in ln:
                should_skip = True
                break
        if not should_skip:
            new_pinned.append(ln)

    if add_missions:
        insert_idx = 1
        for m in add_missions:
            new_pinned.insert(insert_idx, m)
            insert_idx += 1

    if new_note:
        note_idx = -1
        for i, ln in enumerate(new_pinned):
            if "PR #527" in ln or "pinned-mission liveness check" in ln or "핀 정리" in ln:
                note_idx = i
                break
        if note_idx != -1:
            new_pinned[note_idx] = new_note
        else:
            new_pinned.append(new_note)

    return "\n".join(lines[:pinned_start] + new_pinned + lines[pinned_end:])


def main():
    parser = argparse.ArgumentParser(description="Update pinned missions in fix_plan.md")
    parser.add_argument("--file", required=True, help="Path to fix_plan.md")
    parser.add_argument("--graduate", action="append", default=[], help="Substring of mission line to graduate/remove")
    parser.add_argument("--add-mission", action="append", default=[], help="New mission bullet line to add")
    parser.add_argument("--note", help="New explanatory note line")
    parser.add_argument("--dry-run", action="store_true", help="Print result without writing")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    with io.open(args.file, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = update_pinned_block(content, args.graduate, args.add_mission, args.note)

    if args.dry_run:
        print("--- Dry-run: First 25 lines of updated file ---")
        for line in new_content.split("\n")[:25]:
            print(line)
        return

    atomic_write(args.file, new_content)
    print(f"Successfully updated pinned missions in {args.file}")


if __name__ == "__main__":
    main()
