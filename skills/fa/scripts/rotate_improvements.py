#!/usr/bin/env python3
"""rotate_improvements.py -- Rotate resolved items from improvements.md to improvements.archive.md."""

import argparse
import os
import re
import sys
import tempfile

RESOLVED_TAG_PREFIXES = {
    'APPLIED',
    'IMPLEMENTED',
    'ALREADY-IMPLEMENTED',
    'NO-ACTION',
    'CONFIRMED-WORKING',
    'ADJUDICATED',
    'ACTIONED',
    'MAPPED-TO-EXISTING',
    'RESOLVED',
    'DONE',
}

TAG_REGEX = re.compile(r'\*\*Tag\*\*:\s*(\[[^\]]+\])', re.IGNORECASE)

def is_resolved_tag(tag: str) -> bool:
    if not tag or not tag.startswith('[') or not tag.endswith(']'):
        return False
    inner = tag[1:-1].strip()
    prefix = inner.split(':', 1)[0].strip().upper()
    return prefix in RESOLVED_TAG_PREFIXES

def parse_improvements(content: str):
    """Parses improvements markdown into (preamble, sections, active, resolved).

    Structure typically:
    Header / preamble
    ## [Date] Section
    ### Item Title
    - **Tag**: [STATUS]
    - Details...

    Non-item content is returned, not discarded. `preamble` is everything before
    the first heading; `sections` maps each `## ` heading line to the prose that
    follows it before its first `### ` item. Both were previously collected into
    a local list that was never returned, so rewriting the source silently
    deleted them -- and because they were not written to the archive either, the
    content was gone from both files with no backup.
    """
    lines = content.splitlines(keepends=True)

    preamble_lines = []
    sections = {}  # h2 line -> prose lines preceding its first item (insertion-ordered)
    items = [] # list of (header_hierarchy, item_lines, tag)

    current_h2 = ""
    current_h3 = ""
    current_lines = []
    in_item = False

    for line in lines:
        if line.startswith('## '):
            if in_item and current_lines:
                items.append((current_h2, current_h3, current_lines))
                current_lines = []
                in_item = False
            current_h2 = line
            sections.setdefault(current_h2, [])
        elif line.startswith('### '):
            if in_item and current_lines:
                items.append((current_h2, current_h3, current_lines))
                current_lines = []
            current_h3 = line
            in_item = True
            current_lines = [line]
        elif in_item:
            current_lines.append(line)
        elif current_h2:
            # Prose between a `## ` heading and its first item belongs to that
            # section, not to the file preamble.
            sections.setdefault(current_h2, []).append(line)
        else:
            preamble_lines.append(line)

    if in_item and current_lines:
        items.append((current_h2, current_h3, current_lines))

    active_entries = []
    resolved_entries = []
    
    for h2, h3, item_lines in items:
        item_text = "".join(item_lines)
        match = TAG_REGEX.search(item_text)
        tag = match.group(1) if match else ""
        
        entry = {
            'h2': h2,
            'h3': h3,
            'lines': item_lines,
            'text': item_text,
            'tag': tag
        }
        
        if is_resolved_tag(tag):
            resolved_entries.append(entry)
        else:
            active_entries.append(entry)

    return preamble_lines, sections, active_entries, resolved_entries

def format_entries(entries, archive_link=None, preamble=None, sections=None):
    """Rebuilds the active ledger, preserving non-item content.

    The original preamble is re-emitted verbatim when present; the hardcoded
    header is only a fallback for files that have none. Section prose is emitted
    under its heading -- including for sections whose items were all archived,
    which would otherwise drop the prose along with them.
    """
    sections = sections or {}
    preamble_text = "".join(preamble or [])

    out = []
    if preamble_text.strip():
        out.append(preamble_text.rstrip('\n') + "\n\n")
    else:
        out.append("# Improvements Ledger\n\n")

    # Don't duplicate an archive banner the preserved preamble already carries.
    if archive_link and 'archive-link:' not in preamble_text:
        out.append(f"<!-- archive-link: {archive_link} -->\n\n")
        out.append(f"> 📦 **Archived Items**: Past resolved items are archived in [{archive_link}]({archive_link}).\n\n")

    entries_by_h2 = {}
    for e in entries:
        entries_by_h2.setdefault(e['h2'], []).append(e)

    # Emit in original section order, then any headings that only appear on
    # entries (defensive: an entry whose h2 was never recorded as a section).
    ordered_h2 = list(sections.keys())
    for e in entries:
        if e['h2'] not in ordered_h2:
            ordered_h2.append(e['h2'])

    for h2 in ordered_h2:
        section_entries = entries_by_h2.get(h2, [])
        prose = "".join(sections.get(h2, []))
        if not section_entries and not prose.strip():
            continue
        if h2:
            heading = h2 if h2.endswith('\n') else h2 + '\n'
            out.append(f"\n{heading}\n")
        if prose.strip():
            out.append(prose.rstrip('\n') + "\n\n")
        for e in section_entries:
            body = "".join(e['lines'])
            out.append(body)
            if not body.endswith('\n'):
                out.append('\n')
    return "".join(out)

def rotate_file(src_path: str, archive_path: str, dry_run: bool = False) -> dict:
    if not os.path.exists(src_path):
        return {'src': src_path, 'resolved_count': 0, 'active_count': 0, 'status': 'file_not_found'}
        
    with open(src_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    preamble, sections, active, resolved = parse_improvements(content)
    stats = {
        'src': src_path,
        'archive': archive_path,
        'resolved_count': len(resolved),
        'active_count': len(active),
        'dry_run': dry_run
    }
    
    if dry_run or len(resolved) == 0:
        return stats
        
    # Prepare archive content
    archive_basename = os.path.basename(archive_path)
    active_text = format_entries(
        active,
        archive_link=archive_basename,
        preamble=preamble,
        sections=sections,
    )
    
    archive_existing = ""
    if os.path.exists(archive_path):
        with open(archive_path, 'r', encoding='utf-8') as f:
            archive_existing = f.read()
            
    # Append resolved entries
    resolved_formatted = ""
    current_h2 = None
    for e in resolved:
        if e['h2'] and e['h2'] != current_h2:
            current_h2 = e['h2']
            resolved_formatted += f"\n{current_h2}\n"
        resolved_formatted += "".join(e['lines']) + "\n"
        
    if not archive_existing:
        archive_text = f"# Improvements Archive Ledger\n\n> Historical record of resolved, applied, and adjudicated improvement proposals.\n\n{resolved_formatted}"
    else:
        archive_text = archive_existing.rstrip() + "\n\n" + resolved_formatted.lstrip()
        
    os.makedirs(os.path.dirname(archive_path) or '.', exist_ok=True)
    # Write the archive first and only truncate the source once it is durable.
    # Both writes go through a temp file + os.replace so an interruption can
    # never leave a half-written ledger: previously these were two plain
    # open(...,'w') calls, and a crash between them destroyed the source with no
    # backup and no recovery path.
    _atomic_write(archive_path, archive_text.strip() + '\n')
    _atomic_write(src_path, active_text.strip() + '\n')

    return stats

def _atomic_write(path: str, text: str) -> None:
    directory = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(dir=directory, prefix='.rotate-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', '-f', help='Path to improvements.md')
    parser.add_argument('--archive-file', '-a', help='Path to improvements.archive.md')
    parser.add_argument('--dry-run', action='store_true', help='Preview rotation counts without writing')
    parser.add_argument('--all', action='store_true', help='Rotate all known improvements.md locations (.agents and .ralph)')
    args = parser.parse_args()
    
    targets = []
    if args.all:
        for p in ['.agents/improvements.md', '.ralph/improvements.md']:
            if os.path.exists(p):
                targets.append((p, p.replace('.md', '.archive.md')))
    elif args.file:
        arc = args.archive_file or args.file.replace('.md', '.archive.md')
        targets.append((args.file, arc))
    else:
        # Default probe
        default_file = '.agents/improvements.md' if os.path.exists('.agents/improvements.md') else '.ralph/improvements.md'
        targets.append((default_file, default_file.replace('.md', '.archive.md')))
        
    for src, arc in targets:
        res = rotate_file(src, arc, dry_run=args.dry_run)
        print(f"[{'DRY-RUN' if args.dry_run else 'DONE'}] {src} -> {arc}: {res['resolved_count']} archived, {res['active_count']} retained")

if __name__ == '__main__':
    main()
