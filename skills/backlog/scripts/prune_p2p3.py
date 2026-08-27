#!/usr/bin/env python3
"""
prune_p2p3.py - Dual-Routing Prune for P2/P3 tasks:
  1. Issue-tracked (Plane/GitHub Issue) ──→ Purged from fix_plan.md (Offloaded to Plane SSOT)
  2. Non-issue (local untracked)       ──→ Demoted to ## TODO backlog

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
    "## Deep Tasks",
]

TODO_SECTION_HEADERS = [
    "## TODO",
]

ACTIVE_TOOLING_KEYWORDS = [
    "guard",
    "bash-guard",
    "ask-guard",
    "check-ask-payload",
    "hook",
    "bats",
    "pre-commit",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Dual-routing prune for P2/P3 tasks (Issue -> Plane purge, Non-issue -> ## TODO).")
    parser.add_argument("--file", help="Path to fix_plan.md / checklist.md")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of P2/P3 items to process per file (default: 10)")
    parser.add_argument("--all", action="store_true", help="Process ALL matching P2/P3 items without limit")
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
        
    def has_issue_tracking(self):
        body_text = "".join(self.full_lines)
        return bool(re.search(
            r"https?://(?:plane\.[a-z0-9.-]+/[^\s]+|github\.com/[^/\s]+/[^/\s]+/issues/\d+)|\[(?:ES6KR|AIAUTO|DTWEB|INFRA)-\d+\]|Issue\s+#\d+",
            body_text,
            re.IGNORECASE
        ))

    def get_issue_identifier(self):
        body_text = "".join(self.full_lines)
        m = re.search(r"https?://plane\.[a-z0-9.-]+/[^/\s]+/browse/([A-Za-z0-9_-]+-\d+)|\[([A-Za-z0-9_-]+-\d+)\]", body_text)
        if m:
            return m.group(1) or m.group(2)
        m_gh = re.search(r"https?://github\.com/([^/\s]+/[^/\s]+)/issues/(\d+)|Issue\s+#(\d+)", body_text)
        if m_gh:
            if m_gh.group(1) and m_gh.group(2):
                return f"{m_gh.group(1)}#{m_gh.group(2)}"
            return f"Issue#{m_gh.group(3)}"
        return None

    def score(self):
        # P3 items processed before P2
        p_score = 30 if self.priority == 'P3' else 20
        ext_score = 10 if self.classification == 'external' else 0
        # Priority Tasks processed before Deep Tasks
        sec_score = 5 if "Priority" in self.section_name or "우선" in self.section_name else 0
        return p_score + ext_score + sec_score

    def check_anomalies(self):
        warnings = []
        body_text = "".join(self.full_lines)
        
        # Check if body contains P0/P1 mentions (potential priority escalation note)
        if re.search(r"P[01]\b|상향|escalat", body_text, re.IGNORECASE):
            warnings.append("Mentions P0/P1 in body text")
            
        # Check if item relates to active tooling or guards
        for kw in ACTIVE_TOOLING_KEYWORDS:
            if kw in body_text.lower():
                warnings.append(f"Active tooling keyword '{kw}'")
                break
                
        return warnings


def scan_all_p2p3(lines):
    target_headers = ACTIVE_SECTION_HEADERS + TODO_SECTION_HEADERS
    in_target_section = False
    cur_section = ""
    tasks = []
    current_item = None
    
    for i, line in enumerate(lines):
        if line.startswith("## "):
            sec_header = line.strip()
            if any(sec_header.startswith(h) for h in target_headers):
                if current_item:
                    tasks.append(current_item)
                    current_item = None
                in_target_section = True
                cur_section = sec_header
                continue
            else:
                if current_item:
                    tasks.append(current_item)
                    current_item = None
                in_target_section = False
                cur_section = ""
                continue
            
        if not in_target_section:
            continue
            
        # Top-level task line
        if re.match(r"^-\s*\[", line):
            if current_item:
                tasks.append(current_item)
                current_item = None
                
            # 1. Option A: P0 / P1 Early Exclusion Guard (HARD STOP)
            if (re.search(r"^-\s*\[(?:BLOCKED:)?P[01](?::[^\]]+)?\]", line) or 
                re.search(r"^-\s*\[[ x/]\]\s*(?:\[[A-Za-z0-9_-]+\]\s*)*\[(?:BLOCKED:)?P[01]", line)):
                continue

            # 2. Option A: Strict Task Marker Prefix Anchoring (HARD STOP)
            # Pattern A: - [BLOCKED:P2:selfable] or - [P3:external]
            m_p = re.search(r"^-\s*\[(?:BLOCKED:)?(P[23])(?::([^\]]+))?\]", line)
            
            # Pattern B: - [ ] [P2:selfable] or - [ ] [BLOCKED:P3:external] or - [ ] [INFRA-59] [P2:selfable]
            if not m_p:
                m_p = re.search(r"^-\s*\[[ x/]\]\s*(?:\[[A-Za-z0-9_-]+\]\s*)*\[(?:BLOCKED:)?(P[23])(?::([^\]]+))?\]", line)
                
            # Pattern C: - [BLOCKED:P2] without reason suffix
            if not m_p:
                m_p = re.search(r"^-\s*\[(?:BLOCKED:)?(P[23])\]", line)

            if m_p:
                p_val = m_p.group(1)
                c_val = m_p.group(2) if (m_p.lastindex and m_p.lastindex >= 2 and m_p.group(2)) else "selfable"
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


def apply_dual_prune(file_path, items_to_purge, items_to_todo):
    content = Path(file_path).read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    
    # 1. Collect all indices to remove
    remove_indices = set()
    for t in items_to_purge:
        for idx in range(t.start_idx, t.end_idx + 1):
            remove_indices.add(idx)
            
    todo_blocks_to_insert = []
    for t in items_to_todo:
        # Only remove and re-insert if it's coming from an active section
        if not any(t.section_name.startswith(h) for h in TODO_SECTION_HEADERS):
            for idx in range(t.start_idx, t.end_idx + 1):
                remove_indices.add(idx)
            todo_blocks_to_insert.extend(t.full_lines)
            
    # 2. Rebuild lines without purged/moved items
    new_lines = [l for i, l in enumerate(lines) if i not in remove_indices]
    
    # 3. If there are items to insert into ## TODO
    if todo_blocks_to_insert:
        todo_idx = -1
        for i, line in enumerate(new_lines):
            if line.startswith("## TODO"):
                todo_idx = i
                break
                
        if todo_idx == -1:
            insert_before = -1
            for i, line in enumerate(new_lines):
                if line.startswith("## Plan Drafts") or line.startswith("## Completed") or line.startswith("## REPEAT"):
                    insert_before = i
                    break
            if insert_before == -1:
                insert_before = len(new_lines)
                
            insertion = ["\n", "## TODO\n", "\n"] + todo_blocks_to_insert
            new_lines = new_lines[:insert_before] + insertion + new_lines[insert_before:]
        else:
            insert_pos = todo_idx + 1
            while insert_pos < len(new_lines) and new_lines[insert_pos].strip() == "":
                insert_pos += 1
            new_lines = new_lines[:insert_pos] + todo_blocks_to_insert + ["\n"] + new_lines[insert_pos:]
            
    # 4. Write back
    Path(file_path).write_text("".join(new_lines), encoding="utf-8")
    orig_kb = len(content.encode("utf-8")) / 1024
    new_kb = len("".join(new_lines).encode("utf-8")) / 1024
    print(f"[{file_path.name}] Dual-Prune applied: {len(items_to_purge)} issue-tracked items purged to Plane, {len(todo_blocks_to_insert)} non-issue items moved to ## TODO ({orig_kb:.1f} KB -> {new_kb:.1f} KB, -{orig_kb - new_kb:.1f} KB).")


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
    print(f"=== /backlog --prune [Dual-Routing: Issue -> Plane Purge, Non-Issue -> ## TODO] [limit={limit_str}, mode={mode_str}] ===")
    
    total_purged = 0
    total_todo = 0
    total_anomalies = 0
    
    for tf in target_files:
        content = tf.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        all_p2p3 = scan_all_p2p3(lines)
        
        # Split into Dual-Routing categories
        items_purge = [t for t in all_p2p3 if t.has_issue_tracking()]
        items_todo = [t for t in all_p2p3 if not t.has_issue_tracking()]
        
        if not args.all:
            items_purge = sorted(items_purge, key=lambda t: t.score(), reverse=True)[:args.limit]
            items_todo = sorted(items_todo, key=lambda t: t.score(), reverse=True)[:args.limit]
            
        print(f"\nTarget File: {tf}")
        print(f"Total P2/P3 scanned: {len(all_p2p3)} ➔ [Plane-Purge: {len(items_purge)} items, ## TODO: {len(items_todo)} items]")
        
        print("\n  [Category 1: Plane-Offload Purge (Issue-Tracked)]")
        if not items_purge:
            print("    (None)")
        for idx, t in enumerate(items_purge, 1):
            hdr = t.header_text
            if len(hdr) > 95:
                hdr = hdr[:92] + "..."
            issue_id = t.get_issue_identifier()
            anomalies = t.check_anomalies()
            warn_str = f" ⚠️ [{', '.join(anomalies)}]" if anomalies else ""
            if anomalies:
                total_anomalies += len(anomalies)
            print(f"    {idx:2d}. [{t.priority}:{t.classification}] ({t.section_name}) 🔗 [{issue_id}] {hdr}{warn_str}")
            
        print("\n  [Category 2: Local ## TODO Backlog (Non-Issue)]")
        if not items_todo:
            print("    (None)")
        for idx, t in enumerate(items_todo, 1):
            hdr = t.header_text
            if len(hdr) > 95:
                hdr = hdr[:92] + "..."
            anomalies = t.check_anomalies()
            warn_str = f" ⚠️ [{', '.join(anomalies)}]" if anomalies else ""
            if anomalies:
                total_anomalies += len(anomalies)
            print(f"    {idx:2d}. [{t.priority}:{t.classification}] ({t.section_name}) 📄 {hdr}{warn_str}")
            
        total_purged += len(items_purge)
        total_todo += len(items_todo)
        
        if not args.dry_run:
            apply_dual_prune(tf, items_purge, items_todo)

    if args.dry_run:
        print("\n--- Dry-Run Dual-Routing Summary ---")
        print(f"Total candidates: {total_purged + total_todo} (Plane-Purge: {total_purged}, ## TODO: {total_todo})")
        if total_anomalies > 0:
            print(f"⚠️ Flagged {total_anomalies} items with notices (P0/P1 body text or active tooling).")
        else:
            print("✅ All items clean.")


if __name__ == "__main__":
    main()
