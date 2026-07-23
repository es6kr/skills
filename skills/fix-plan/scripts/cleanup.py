#!/usr/bin/env python3
# cleanup.py — Parse fix_plan.md / checklist.md list tree, move completed [x] items, and archive old logs.
# Usage: python3 cleanup.py [--file <path>] [--cutoff <YYYY-MM-DD>] [--period monthly|weekly] [--dry-run]

import sys
import os
import re
import codecs
import argparse
from datetime import datetime

def parse_args():
    parser = argparse.ArgumentParser(description="Clean up completed items and archive older entries in fix plans.")
    parser.add_argument("--file", help="Path to the fix_plan.md or checklist.md file.")
    parser.add_argument("--cutoff", help="Cutoff date (YYYY-MM-DD) for archiving. Defaults to the start of the current month.")
    parser.add_argument("--period", choices=["monthly", "weekly"], default="monthly", help="Archive period cadence (default: monthly).")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to files.")
    return parser.parse_args()

class Node:
    def __init__(self, text, indent, is_list_item=False, checked=None, marker_type=None, blocked_marker=False):
        self.text = text
        self.indent = indent
        self.is_list_item = is_list_item
        self.checked = checked
        self.marker_type = marker_type
        self.blocked_marker = blocked_marker
        self.children = []

def parse_line(line):
    m = re.match(r"^(\s*)(-\s*|[*]\s*|[+]\s*|\d+\.\s+)(.*)$", line)
    if m:
        indent = len(m.group(1))
        marker = m.group(2)
        rest = m.group(3)
        checked = None
        if rest.startswith("[x]"):
            checked = True
            text = rest[3:].strip()
        elif rest.startswith("[ ]"):
            checked = False
            text = rest[3:].strip()
        elif rest.startswith("[BLOCKED"):
            # Standard standalone marker ("- [BLOCKED] item") — unresolved for the
            # descendants gate, but must round-trip with its original marker
            # (never rewritten to "- [ ] [BLOCKED]").
            checked = False
            text = rest
            return Node(text, indent, is_list_item=True, checked=checked, marker_type=marker, blocked_marker=True)
        else:
            text = rest
        return Node(text, indent, is_list_item=True, checked=checked, marker_type=marker)
    return Node(line, -1)

def build_tree(lines_list):
    forest = []
    stack = []
    for line in lines_list:
        node = parse_line(line)
        if not node.is_list_item:
            forest.append(node)
            stack = []
            continue
        while stack and stack[-1].indent >= node.indent:
            stack.pop()
        if stack:
            stack[-1].children.append(node)
        else:
            forest.append(node)
        stack.append(node)
    return forest

def all_descendants_checked(n):
    for c in n.children:
        if c.checked is False:
            return False
        if not all_descendants_checked(c):
            return False
    return True

def extract_date(text):
    dates = re.findall(r"\b(202\d-\d{2}-\d{2})\b", text)
    if dates:
        return dates[-1]
    m = re.search(r"\b(202\d-\d{2})\b", text)
    if m:
        return m.group(1) + "-01"
    return datetime.now().strftime("%Y-%m-%d")

def node_to_lines(node):
    lines = []
    
    def get_marker(n):
        if n.checked is True:
            bullet = n.marker_type.strip()
            return f"{bullet} [x] "
        elif n.checked is False:
            if n.blocked_marker:
                return n.marker_type
            bullet = n.marker_type.strip()
            return f"{bullet} [ ] "
        else:
            return n.marker_type

    if node.is_list_item:
        marker = get_marker(node)
        indent_str = " " * node.indent
        lines.append(f"{indent_str}{marker}{node.text}")
    else:
        lines.append(node.text)
    
    def recurse(n):
        if n.is_list_item:
            c_marker = get_marker(n)
            indent_str = " " * n.indent
            lines.append(f"{indent_str}{c_marker}{n.text}")
        else:
            lines.append(n.text)
            
        for child in n.children:
            recurse(child)
            
    for child in node.children:
        recurse(child)
    return lines

def node_to_one_line(node, strip_checkbox=True):
    if node.is_list_item:
        if strip_checkbox:
            bullet = node.marker_type.strip()
            if bullet.endswith('.'):
                marker = f"{bullet} "
            else:
                marker = "- "
        else:
            if node.checked is True:
                bullet = node.marker_type.strip()
                marker = f"{bullet} [x] "
            elif node.checked is False:
                if node.blocked_marker:
                    marker = node.marker_type
                else:
                    bullet = node.marker_type.strip()
                    marker = f"{bullet} [ ] "
            else:
                marker = node.marker_type
        indent_str = " " * node.indent
        return f"{indent_str}{marker}{node.text}"
    else:
        return node.text

def node_to_completed_block(node, strip_checkbox=True):
    """Render a node AND all its descendants as a block of lines for the
    Completed section — unlike node_to_one_line, this recurses into
    node.children so a completed subtree's detail is never silently dropped.
    Synthesizing N child bullets into one prose summary line requires
    semantic judgment a script cannot safely perform, so this preserves the
    full text instead (checkbox markers stripped per the Completed-section
    convention; the caller/human can hand-condense later if desired)."""
    lines = []

    def marker_for(n):
        if n.blocked_marker:
            # All descendants of a node selected for move are checked==True
            # (is_top_level_complete/is_subtree both require
            # all_descendants_checked), so a live [BLOCKED] child should not
            # occur here in practice — kept as a defensive fallback only.
            return n.marker_type
        if strip_checkbox:
            bullet = n.marker_type.strip()
            return f"{bullet} " if bullet.endswith('.') else "- "
        if n.checked is True:
            return f"{n.marker_type.strip()} [x] "
        if n.checked is False:
            return f"{n.marker_type.strip()} [ ] "
        return n.marker_type

    def emit(n):
        if n.is_list_item:
            indent_str = " " * n.indent
            lines.append(f"{indent_str}{marker_for(n)}{n.text}")
        else:
            lines.append(n.text)
        for child in n.children:
            emit(child)

    emit(node)
    return lines

def main():
    args = parse_args()
    
    # 1. Resolve file path
    file_path = args.file
    if not file_path:
        # Search common paths
        cwd = os.getcwd()
        candidates = [
            os.path.join(cwd, ".ralph", "fix_plan.md"),
            os.path.join(cwd, "fix_plan.md"),
            os.path.join(cwd, "checklist.md")
        ]
        for cand in candidates:
            if os.path.exists(cand):
                file_path = cand
                break
                
    if not file_path or not os.path.exists(file_path):
        print(f"ERROR: Target fix plan file not found. Specify via --file.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Target File: {file_path}")
    
    # 2. Resolve cutoff date
    cutoff_date = args.cutoff
    if not cutoff_date:
        # Defaults to YYYY-MM-01 of the current date
        cutoff_date = datetime.now().strftime("%Y-%m-01")
    print(f"Archive Cutoff Date: {cutoff_date}")

    # Read file
    with open(file_path, 'rb') as f:
        raw = f.read()

    has_bom = raw.startswith(codecs.BOM_UTF8)
    content = raw.decode('utf-8-sig' if has_bom else 'utf-8')
    lines = content.splitlines()

    # Group by sections
    sections = []
    current_sec_header = None
    current_sec_lines = []

    for line in lines:
        if line.startswith("## ") or line.startswith("# "):
            if current_sec_header is not None or current_sec_lines:
                sections.append((current_sec_header, current_sec_lines))
            current_sec_header = line
            current_sec_lines = []
        else:
            current_sec_lines.append(line)
    if current_sec_header is not None or current_sec_lines:
        sections.append((current_sec_header, current_sec_lines))

    completed_entries = []
    new_sections = []

    for header, sec_lines in sections:
        if header is None:
            new_sections.append((header, sec_lines))
            continue
        
        if "## Completed" in header:
            forest = build_tree(sec_lines)
            for node in forest:
                if node.is_list_item and node.checked is True:
                    completed_entries.append({
                        "date": extract_date(node.text),
                        "node": node
                    })
                elif node.is_list_item and node.text.strip():
                    date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", node.text)
                    if date_match:
                        completed_entries.append({
                            "date": date_match.group(1),
                            "node": node
                        })
                    else:
                        completed_entries.append({
                            "date": extract_date(node.text),
                            "node": node
                        })
            continue
            
        if "## REPEAT" in header:
            new_sections.append((header, sec_lines))
            continue
            
        forest = build_tree(sec_lines)

        def process_nodes(node_list, parent_active=False):
            keep_nodes = []
            for node in node_list:
                if not node.is_list_item:
                    keep_nodes.append(node)
                    continue

                is_completed = (node.checked is True)

                is_subtree = False
                if parent_active and is_completed:
                    has_keyword = any(kw in node.text.upper() for kw in ["MERGED", "CLOSED", "완료", "PR #", "ISSUE #"])
                    if all_descendants_checked(node) and has_keyword:
                        is_subtree = True

                # A top-level [x] item only fully archives when every descendant is also
                # checked. A completed parent with a still-open child (e.g. a resolved bug
                # report whose separately-tracked upstream sub-issue remains [ ]) must NOT
                # be swept wholesale into Completed/archive — that silently buries the open
                # child in a monthly cold-storage partition file with no live-tracker trace.
                is_top_level_complete = (
                    not parent_active and is_completed and all_descendants_checked(node)
                )

                if is_top_level_complete or is_subtree:
                    completed_entries.append({
                        "date": extract_date(node.text),
                        "node": node
                    })
                else:
                    node.children = process_nodes(node.children, parent_active=True)
                    keep_nodes.append(node)
            return keep_nodes

        remaining_forest = process_nodes(forest)
        
        # Reconstruct section lines
        new_sec_lines = []
        for node in remaining_forest:
            new_sec_lines.extend(node_to_lines(node))
        new_sections.append((header, new_sec_lines))

    # Partition completed items
    archive_by_period = {}
    stay_completed = []

    for entry in completed_entries:
        date_str = entry["date"]
        if date_str < cutoff_date:
            if args.period == "monthly":
                period_key = date_str[:7] # YYYY-MM
            else:
                # ISO week YYYY-Www
                dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
                year, week, _ = dt_obj.isocalendar()
                period_key = f"{year}-W{week:02d}"
                
            if period_key not in archive_by_period:
                archive_by_period[period_key] = []
            archive_by_period[period_key].append(entry)
        else:
            stay_completed.append(entry)

    # Sort Completed descending to match existing fix_plan.md structure
    stay_completed.sort(key=lambda x: x["date"], reverse=True)

    # Generate new ## Completed lines
    completed_lines = [""]
    for entry in stay_completed:
        completed_lines.extend(node_to_completed_block(entry["node"], strip_checkbox=True))
        completed_lines.append("") # blank line between items

    # Add the new ## Completed section before ## REPEAT or at the right place
    final_sections = []
    inserted_completed = False

    for header, sec_lines in new_sections:
        if header and "## REPEAT" in header:
            final_sections.append(("## Completed", completed_lines))
            inserted_completed = True
        final_sections.append((header, sec_lines))

    if not inserted_completed:
        final_sections.append(("## Completed", completed_lines))

    # Re-assemble everything
    output_lines = []
    for header, sec_lines in final_sections:
        if header:
            output_lines.append(header)
        output_lines.extend(sec_lines)

    output_content = "\n".join(output_lines)
    
    if args.dry_run:
        print("\n=== DRY RUN MODE: No files will be modified ===")
        print(f"Total completed entries found: {len(completed_entries)}")
        print(f"Remaining in ## Completed: {len(stay_completed)}")
        print(f"To be archived by {args.period}:")
        for period, entries in sorted(archive_by_period.items()):
            print(f"  - {period}: {len(entries)} entries")
        sys.exit(0)

    # Write output to target file
    if has_bom:
        output_bytes = codecs.BOM_UTF8 + output_content.encode('utf-8')
    else:
        output_bytes = output_content.encode('utf-8')

    # Backup original file — timestamped slot so a rerun cannot clobber the only good copy
    backup_path = f"{file_path}.{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
    with open(backup_path, 'wb') as f:
        f.write(raw)
    print(f"Backup created at {backup_path}")

    # Write new file content atomically — a crash mid-write must not truncate the live tracker
    tmp_path = file_path + ".tmp"
    with open(tmp_path, 'wb') as f:
        f.write(output_bytes)
    os.replace(tmp_path, file_path)
    print(f"Updated {os.path.basename(file_path)} successfully.")

    # Write archives
    tracker_dir = os.path.dirname(file_path)
    bak_dir = os.path.join(tracker_dir, ".bak")
    os.makedirs(bak_dir, exist_ok=True)
    
    file_stem, _ = os.path.splitext(os.path.basename(file_path))
    
    for period, entries in sorted(archive_by_period.items()):
        archive_file = os.path.join(bak_dir, f"{file_stem}-completed-{period}.md")
        
        # Sort entries ascending for archives per move.md spec
        entries.sort(key=lambda x: x["date"])
        
        existing_content = ""
        archived_lines = []
        if os.path.exists(archive_file):
            # utf-8-sig on read strips the BOM the write below prepends —
            # plain utf-8 here stacked one more BOM per archive append.
            with open(archive_file, 'r', encoding='utf-8-sig') as af:
                existing_content = af.read()
            archived_lines.append(existing_content.rstrip())
        else:
            archived_lines.append(f"# Archived Completed — {period}\n")
            
        added_count = 0
        for entry in entries:
            # Idempotency check: check if the entry's unique text is already in the file.
            if entry["node"].text in existing_content:
                print(f"Skipping duplicate archive entry: {entry['node'].text}")
                continue
            archived_lines.extend(node_to_completed_block(entry["node"], strip_checkbox=True))
            archived_lines.append("")
            added_count += 1
            
        archive_content = "\n".join(archived_lines)
        with open(archive_file, 'w', encoding='utf-8-sig') as af:
            af.write(archive_content)
        print(f"Archived {added_count} entries to {archive_file} (skipped {len(entries) - added_count} duplicates)")

if __name__ == "__main__":
    main()
