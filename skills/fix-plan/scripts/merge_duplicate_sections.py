#!/usr/bin/env python3
"""
merge_duplicate_sections.py - Merge duplicate ## TODO sections in fix_plan.md into a single canonical ## TODO section.

Usage:
  python merge_duplicate_sections.py --file <path>
"""

import sys
import re
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Merge duplicate sections in fix_plan.md.")
    parser.add_argument("--file", required=True, help="Path to fix_plan.md")
    parser.add_argument("--dry-run", action="store_true", help="Preview only without writing")
    return parser.parse_args()


def merge_sections(file_path, dry_run=False):
    content = Path(file_path).read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    
    # Identify sections
    section_ranges = [] # list of (header_line_idx, header_name, start_idx, end_idx)
    cur_hdr_idx = -1
    cur_hdr = ""
    
    for i, line in enumerate(lines):
        if line.startswith("## "):
            if cur_hdr_idx != -1:
                section_ranges.append((cur_hdr_idx, cur_hdr, cur_hdr_idx, i - 1))
            cur_hdr_idx = i
            cur_hdr = line.strip()
            
    if cur_hdr_idx != -1:
        section_ranges.append((cur_hdr_idx, cur_hdr, cur_hdr_idx, len(lines) - 1))
        
    todo_sections = [s for s in section_ranges if s[1].startswith("## TODO")]
    print(f"Found {len(todo_sections)} '## TODO' sections in {file_path}")
    for idx, s in enumerate(todo_sections, 1):
        print(f"  Instance {idx}: lines {s[2]+1} to {s[3]+1} ({s[3] - s[2] + 1} lines)")
        
    if len(todo_sections) <= 1:
        print("No duplicate ## TODO sections found.")
        return
        
    # Extract lines for each TODO section
    all_todo_body_lines = []
    remove_indices = set()
    
    for s in todo_sections:
        # Mark all lines of this section for removal
        for idx in range(s[2], s[3] + 1):
            remove_indices.add(idx)
        # Extract body lines (skip the ## TODO header itself)
        body = lines[s[2]+1 : s[3]+1]
        all_todo_body_lines.extend(body)
        
    # Clean up empty lines around body
    clean_todo_body = []
    for l in all_todo_body_lines:
        clean_todo_body.append(l)
        
    # Rebuild base lines without any TODO sections
    new_lines = [l for i, l in enumerate(lines) if i not in remove_indices]
    
    # Find insertion point: Before ## Completed or ## REPEAT, or after ## Plan Drafts
    insert_idx = -1
    for i, line in enumerate(new_lines):
        if line.startswith("## Completed") or line.startswith("## REPEAT"):
            insert_idx = i
            break
            
    if insert_idx == -1:
        insert_idx = len(new_lines)
        
    # Compose single canonical ## TODO section
    todo_block = ["\n", "## TODO\n", "\n"] + clean_todo_body
    final_lines = new_lines[:insert_idx] + todo_block + new_lines[insert_idx:]
    
    if dry_run:
        print(f"[DRY-RUN] Would merge {len(todo_sections)} ## TODO sections into 1 canonical section at line {insert_idx+1}.")
    else:
        Path(file_path).write_text("".join(final_lines), encoding="utf-8")
        print(f"Successfully merged {len(todo_sections)} ## TODO sections into 1 canonical section before line {insert_idx+1}.")


if __name__ == "__main__":
    args = parse_args()
    merge_sections(args.file, dry_run=args.dry_run)
