#!/usr/bin/env python3
"""append_pipeline_log.py — Append a new entry to '## Pipeline Execution Log' in fix_plan.md / checklist.md.

Usage:
  python append_pipeline_log.py --file <path> --entry-file <path>
  python append_pipeline_log.py --file <path> --entry "..."
"""

import os
import sys
import codecs
import argparse
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def parse_args():
    parser = argparse.ArgumentParser(description="Append an entry to Pipeline Execution Log in fix_plan.md")
    parser.add_argument("--file", default=".agents/fix_plan.md", help="Path to fix_plan.md or checklist.md")
    parser.add_argument("--entry", help="Log entry text string")
    parser.add_argument("--entry-file", help="Path to file containing log entry (UTF-8)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    return parser.parse_args()

def main():
    args = parse_args()
    file_path = args.file
    if not os.path.exists(file_path):
        print(f"ERROR: Tracker file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    if args.entry_file:
        with open(args.entry_file, "r", encoding="utf-8") as ef:
            entry_text = ef.read().strip()
    elif args.entry:
        entry_text = args.entry.strip()
    else:
        print("ERROR: Either --entry or --entry-file must be given", file=sys.stderr)
        sys.exit(1)

    with open(file_path, "rb") as f:
        raw = f.read()

    has_bom = raw.startswith(codecs.BOM_UTF8)
    content = raw.decode("utf-8-sig" if has_bom else "utf-8")
    lines = content.splitlines()

    # Find '## Pipeline Execution Log'
    log_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == "## Pipeline Execution Log":
            log_idx = i
            break

    if log_idx == -1:
        print("ERROR: '## Pipeline Execution Log' section not found", file=sys.stderr)
        sys.exit(1)

    entry_lines = entry_text.splitlines()

    # Insert after '## Pipeline Execution Log' (and any blank line immediately after it)
    insert_pos = log_idx + 1
    if insert_pos < len(lines) and lines[insert_pos].strip() == "":
        insert_pos += 1

    # Add entry followed by a blank line
    new_lines = lines[:insert_pos] + entry_lines + [""] + lines[insert_pos:]
    output_content = "\n".join(new_lines)
    if raw.endswith(b"\n") and not output_content.endswith("\n"):
        output_content += "\n"

    if args.dry_run:
        print(f"=== DRY RUN: Would insert {len(entry_lines)} lines at line {insert_pos+1} ===")
        print(entry_text[:200] + "...")
        return

    # Backup
    backup_path = f"{file_path}.{datetime.now().strftime('%Y%m%d-%H%M%S')}.pipelinelog.bak"
    with open(backup_path, "wb") as f:
        f.write(raw)
    print(f"Backup created at {backup_path}")

    # Atomic replace
    if has_bom:
        out_bytes = codecs.BOM_UTF8 + output_content.encode("utf-8")
    else:
        out_bytes = output_content.encode("utf-8")

    tmp_path = file_path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(out_bytes)
    os.replace(tmp_path, file_path)
    print(f"Successfully appended entry to Pipeline Execution Log in {file_path}")

if __name__ == "__main__":
    main()
