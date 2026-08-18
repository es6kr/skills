#!/usr/bin/env python3
"""
triage-fixplan-completed.py

Automates triaging completed `- [x]` items in fix_plan.md:
1. Extracts completed top-level `- [x]` items and their indented child lines (1:1 full text, NO summary).
2. Classifies items into:
   - Plane index candidates (items containing PR URLs, architecture refactors, or explicit Plane backlog tags)
   - Standard completed items (to be moved directly to ## Completed section)
3. Performs 1:1 verbatim movement to ## Completed section with timestamp prefix `YYYY-MM-DD — `.
"""

import sys
import re
import datetime

def parse_completed_blocks(lines, start_line=1, end_line=None):
    if end_line is None:
        end_line = len(lines)

    blocks = []
    current_block = None

    for idx in range(start_line - 1, min(end_line, len(lines))):
        line = lines[idx]
        # Check if line is a top-level completed item
        if re.match(r'^\s*-\s*\[x\]\s+', line):
            if current_block:
                blocks.append(current_block)
            current_block = {
                'start_line': idx + 1,
                'end_line': idx + 1,
                'header': line.rstrip(),
                'lines': [line.rstrip()]
            }
        elif current_block and (line.startswith('  ') or line.startswith('\t') or line.strip() == ''):
            # Indented child line or empty line within block
            if line.strip() == '' and idx + 1 < len(lines) and not (lines[idx+1].startswith('  ') or lines[idx+1].startswith('\t')):
                # Blank line followed by non-indented line ends block
                blocks.append(current_block)
                current_block = None
            else:
                current_block['lines'].append(line.rstrip())
                current_block['end_line'] = idx + 1
        else:
            if current_block:
                blocks.append(current_block)
                current_block = None

    if current_block:
        blocks.append(current_block)

    return blocks

def format_completed_entry(block, date_str=None):
    if date_str is None:
        date_str = datetime.date.today().isoformat()

    lines = block['lines']
    # Insert date prefix after `- [x] ` if not already dated
    header = lines[0]
    m = re.match(r'^(\s*-\s*\[x\]\s+)(.*)$', header)
    if m:
        prefix, rest = m.groups()
        if not re.match(r'^\d{4}-\d{2}-\d{2}\s*—', rest):
            lines[0] = f"{prefix}{date_str} — {rest}"
    
    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: triage-fixplan-completed.py <fix_plan.md_path> [start_line] [end_line]")
        sys.exit(1)

    filepath = sys.argv[1]
    start_line = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    end_line = int(sys.argv[3]) if len(sys.argv) > 3 else None

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    blocks = parse_completed_blocks(lines, start_line, end_line)

    print(f"=== Found {len(blocks)} completed block(s) between L{start_line} and L{end_line or len(lines)} ===")
    for b_idx, block in enumerate(blocks, 1):
        print(f"\n--- Block #{b_idx} (L{block['start_line']}-L{block['end_line']}) ---")
        formatted = format_completed_entry(block)
        print(formatted)

if __name__ == '__main__':
    main()
