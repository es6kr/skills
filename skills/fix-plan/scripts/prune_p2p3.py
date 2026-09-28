#!/usr/bin/env python3
"""
prune_p2p3.py - Prune/demote P2/P3 tasks from active sections (Priority Tasks & Deep Tasks) to ## TODO backlog.

Usage:
  python prune_p2p3.py [--file <path>] [--limit <N>] [--all] [--dry-run]
"""

import sys
import os
import re
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ACTIVE_SECTION_HEADERS = [
    "## Priority Tasks",
    "## 우선 작업",
    "## Deep Tasks",
    "## Fable Target Tasks",
]

def parse_args():
    parser = argparse.ArgumentParser(description="Prune P2/P3 tasks from active sections into ## TODO backlog.")
    parser.add_argument("--file", help="Path to fix_plan.md")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of P2/P3 items to prune/demote per file (default: 10)")
    parser.add_argument("--all", action="store_true", help="Prune ALL matching P2/P3 items without limit")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying file (default: False)")
    return parser.parse_args()


class TaskItem:
    def __init__(self, section_name, start_idx, end_idx, header_text, full_lines, priority, classification):
        self.section_name = section_name
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.header_text = header_text
        self.full_lines = full_lines
        self.priority = priority  # 'P2' or 'P3'
        self.classification = classification  # 'selfable', 'external', etc.
        
    def score(self):
        # P3 items pruned before P2
        p_score = 30 if self.priority == 'P3' else 20
        ext_score = 10 if self.classification == 'external' else 0
        # Priority Tasks pruned before Deep Tasks
        sec_score = 5 if "Priority" in self.section_name or "우선" in self.section_name else 0
        return p_score + ext_score + sec_score


def scan_active_p2p3(lines):
    in_active = False
    cur_section = ""
    tasks = []
    current_item = None
    
    for i, line in enumerate(lines):
        if line.startswith("## "):
            sec_header = line.strip()
            if any(sec_header.startswith(h) for h in ACTIVE_SECTION_HEADERS):
                if current_item:
                    tasks.append(current_item)
                    current_item = None
                in_active = True
                cur_section = sec_header
                continue
            else:
                if current_item:
                    tasks.append(current_item)
                    current_item = None
                in_active = False
                cur_section = ""
                continue
            
        if not in_active:
            continue
            
        # Top-level task line
        if re.match(r"^-\s*\[", line):
            if current_item:
                tasks.append(current_item)
                current_item = None
                
            m_p = re.search(r"\[(?:BLOCKED:)?(P[23])(?::([^\]]+))?\]", line)
            if not m_p:
                m_p = re.search(r"\b(P[23])\b", line)
                
            if m_p:
                p_val = m_p.group(1)
                c_val = m_p.group(2) if m_p.lastindex >= 2 else "selfable"
                current_item = TaskItem(
                    section_name=cur_section,
                    start_idx=i,
                    end_idx=i,
                    header_text=line.strip(),
                    full_lines=[line],
                    priority=p_val,
                    classification=c_val
                )
        else:
            if current_item:
                if line.strip() == "" or line.startswith("  ") or line.startswith("\t"):
                    current_item.end_idx = i
                    current_item.full_lines.append(line)
                else:
                    tasks.append(current_item)
                    current_item = None
                    
    if current_item:
        tasks.append(current_item)
        
    return tasks


def apply_prune(file_path, limit=10, prune_all=False):
    content = Path(file_path).read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    
    tasks = scan_active_p2p3(lines)
    if not tasks:
        print(f"[{file_path.name}] No P2/P3 tasks found in active sections.")
        return
        
    # Sort and take candidates
    tasks_sorted = sorted(tasks, key=lambda t: t.score(), reverse=True)
    to_prune = tasks_sorted if prune_all else tasks_sorted[:limit]
    
    # Collect line indices to remove
    remove_indices = set()
    pruned_text_blocks = []
    for t in to_prune:
        for idx in range(t.start_idx, t.end_idx + 1):
            remove_indices.add(idx)
        pruned_text_blocks.extend(t.full_lines)
        
    # Rebuild lines without pruned items
    new_lines = [l for i, l in enumerate(lines) if i not in remove_indices]
    
    # Find or create ## TODO section
    todo_idx = -1
    for i, line in enumerate(new_lines):
        if line.startswith("## TODO"):
            todo_idx = i
            break
            
    if todo_idx == -1:
        # Insert before ## Plan Drafts or ## Completed
        insert_before = -1
        for i, line in enumerate(new_lines):
            if line.startswith("## Plan Drafts") or line.startswith("## Completed") or line.startswith("## REPEAT"):
                insert_before = i
                break
        if insert_before == -1:
            insert_before = len(new_lines)
            
        insertion = ["\n", "## TODO\n", "\n"] + pruned_text_blocks
        new_lines = new_lines[:insert_before] + insertion + new_lines[insert_before:]
    else:
        # Append to existing ## TODO section (at the start of TODO items)
        insert_pos = todo_idx + 1
        while insert_pos < len(new_lines) and new_lines[insert_pos].strip() == "":
            insert_pos += 1
        new_lines = new_lines[:insert_pos] + pruned_text_blocks + ["\n"] + new_lines[insert_pos:]
        
    # Write back
    Path(file_path).write_text("".join(new_lines), encoding="utf-8")
    print(f"[{file_path.name}] Successfully migrated {len(to_prune)} P2/P3 items to ## TODO and pruned from active sections.")


def main():
    args = parse_args()
    
    target_files = []
    if args.file:
        target_files.append(Path(args.file))
    else:
        home = Path.home()
        candidates = [
            home / "ghq/github.com/es6kr/.agents/fix_plan.md",
            home / "ghq/github.com/daegunsoftDev/.agents/fix_plan.md",
            Path(r"C:\Users\DAEGUNSOFT\ghq\github.com\es6kr\.agents\fix_plan.md"),
            Path(r"C:\Users\DAEGUNSOFT\ghq\github.com\daegunsoftDev\.agents\fix_plan.md"),
        ]
        for c in candidates:
            if c.exists() and c not in target_files:
                target_files.append(c)
                
    mode_str = "DRY-RUN (Preview)" if args.dry_run else "EXECUTE (Applying changes)"
    limit_str = "ALL" if args.all else str(args.limit)
    print(f"=== /fix-plan --prune-p2p3 [limit={limit_str}, mode={mode_str}] ===")
    
    for tf in target_files:
        content = tf.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        tasks = scan_active_p2p3(lines)
        
        print(f"\nTarget File: {tf}")
        print(f"P2/P3 tasks in active sections (Priority & Deep): {len(tasks)}")
        
        tasks_sorted = sorted(tasks, key=lambda t: t.score(), reverse=True)
        candidates = tasks_sorted if args.all else tasks_sorted[:args.limit]
        
        if not candidates:
            print("  (None)")
            continue
            
        print(f"Candidates to migrate to ## TODO (Top {len(candidates)}):")
        for idx, t in enumerate(candidates, 1):
            hdr = t.header_text
            if len(hdr) > 110:
                hdr = hdr[:107] + "..."
            print(f"  {idx:2d}. [{t.priority}:{t.classification}] ({t.section_name}) {hdr}")
            
        if not args.dry_run:
            apply_prune(tf, limit=args.limit, prune_all=args.all)


if __name__ == "__main__":
    main()
