#!/usr/bin/env python3
"""add_pipeline_log.py — Append a new entry to '## Pipeline Execution Log' in fix_plan.md.

Enforces the pinned rule:
- Keep the most recent 3 entries in '## Pipeline Execution Log'.
- Older entries beyond 3 are appended to .agents/pipeline-execution-log-archive.md.

Usage:
    python add_pipeline_log.py --file <path> --entry "<entry text>" [--dry-run]
"""

import argparse
import os
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Add an entry to ## Pipeline Execution Log.")
    parser.add_argument("--file", default=".agents/fix_plan.md", help="Path to fix_plan.md")
    parser.add_argument("--entry", required=True, help="Markdown bullet text for the log entry")
    parser.add_argument("--max-entries", type=int, default=3, help="Max entries to keep in fix_plan.md (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    return parser.parse_args()


def extract_pipeline_log_section(lines):
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "## Pipeline Execution Log":
            start_idx = i
            break

    if start_idx is None:
        return None, None, []

    for i in range(start_idx + 1, len(lines)):
        if lines[i].startswith("## "):
            end_idx = i
            break

    if end_idx is None:
        end_idx = len(lines)

    log_lines = lines[start_idx + 1:end_idx]
    return start_idx, end_idx, log_lines


def parse_entries(log_lines):
    entries = []
    current_entry = []
    for line in log_lines:
        if line.startswith("- "):
            if current_entry:
                entries.append("\n".join(current_entry).strip())
                current_entry = []
            current_entry.append(line)
        elif current_entry:
            current_entry.append(line)
    if current_entry:
        entries.append("\n".join(current_entry).strip())
    return [e for e in entries if e]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    target_path = Path(args.file)
    if not target_path.exists():
        print(f"ERROR: File not found: {target_path}", file=sys.stderr)
        sys.exit(1)

    text = target_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)

    start_idx, end_idx, log_lines = extract_pipeline_log_section(lines)
    if start_idx is None:
        print("ERROR: '## Pipeline Execution Log' section not found.", file=sys.stderr)
        sys.exit(1)

    existing_entries = parse_entries(log_lines)
    new_entry = args.entry.strip()
    if not new_entry.startswith("- "):
        new_entry = "- " + new_entry

    all_entries = [new_entry] + existing_entries

    kept_entries = all_entries[:args.max_entries]
    archived_entries = all_entries[args.max_entries:]

    print(f"[Plan] Total entries: {len(all_entries)}, Keep: {len(kept_entries)}, Archive: {len(archived_entries)}")

    if args.dry_run:
        print("\n--- Kept Entries ---")
        for e in kept_entries:
            print(e[:100] + ("..." if len(e) > 100 else ""))
        if archived_entries:
            print("\n--- Archived Entries ---")
            for e in archived_entries:
                print(e[:100] + ("..." if len(e) > 100 else ""))
        print("\n[DRY RUN] No files modified.")
        return

    # If entries need archiving
    if archived_entries:
        archive_path = target_path.parent / "pipeline-execution-log-archive.md"
        archive_header = ""
        if not archive_path.exists():
            archive_header = "# Pipeline Execution Log Archive\n\n"
        archive_content = "\n\n".join(archived_entries) + "\n\n"
        with open(archive_path, "a", encoding="utf-8") as f:
            if archive_header:
                f.write(archive_header)
            f.write(archive_content)
        print(f"[Archived] {len(archived_entries)} entries appended to {archive_path}")

    # Reconstruct fix_plan.md
    formatted_kept = "\n\n".join(kept_entries)
    new_lines = (
        lines[:start_idx + 1]
        + [""]
        + [formatted_kept]
        + [""]
        + lines[end_idx:]
    )

    new_content = "\n".join(new_lines) + "\n"
    target_path.write_text(new_content, encoding="utf-8")
    print(f"[Success] Added pipeline execution log entry to {target_path}")


if __name__ == "__main__":
    main()
