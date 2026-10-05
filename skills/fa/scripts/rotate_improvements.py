#!/usr/bin/env python3
"""rotate_improvements.py -- Rotate resolved items from improvements.md to improvements.archive.md."""

import argparse
import os
import re
import shutil
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
    """Parses improvements markdown content into (preamble, sections, active, resolved).

    Structure typically:
    Header / preamble
    ## [Date] Section
    (optional section prose)
    ### Item Title
    - **Tag**: [STATUS]
    - Details...

    Everything that is not an entry falls into one of two buckets, and BOTH are
    returned so a caller rewriting the file can put them back. Losing them is not
    cosmetic: this script overwrites its source, so anything it fails to return is
    gone from disk.

    - preamble: lines before the first header
    - section prose: lines after a `##` but before that section's first `###`,
      carried on every entry of that section as `section_prose`
    """
    lines = content.splitlines(keepends=True)

    preamble_lines = []
    items = [] # list of (h2, h3, item_lines)
    section_prose = {} # h2 line -> its prose lines

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
            section_prose.setdefault(current_h2, [])
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
            # Inside a section but ahead of its first entry — belongs to the
            # section, not to the document preamble.
            section_prose[current_h2].append(line)
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
            'tag': tag,
            'section_prose': "".join(section_prose.get(h2, []))
        }

        if is_resolved_tag(tag):
            resolved_entries.append(entry)
        else:
            active_entries.append(entry)

    # `sections` is returned alongside the per-entry copy because prose carried on
    # entries is only recoverable while that section still HAS an entry. When every
    # item in a section is resolved, all of them move to the archive and the prose
    # has no carrier left, so it disappears from both files. The ordered map is the
    # only way format_entries can re-emit such a section.
    sections = {h2: "".join(lines) for h2, lines in section_prose.items()}
    return "".join(preamble_lines), sections, active_entries, resolved_entries

def format_entries(entries, preamble=None, archive_link=None, sections=None):
    # Keep the file's own preamble. Regenerating a fixed header here would discard
    # whatever the ledger carried above its first section.
    if preamble and preamble.strip():
        out = [preamble if preamble.endswith('\n') else preamble + '\n']
    else:
        out = ["# Improvements Ledger\n\n"]

    # Only introduce the archive pointer when the preserved preamble does not
    # already carry one — otherwise every rotation appends another copy.
    if archive_link and 'archive-link' not in (preamble or ''):
        out.append(f"<!-- archive-link: {archive_link} -->\n\n")
        out.append(f"> 📦 **Archived Items**: Past resolved items are archived in [{archive_link}]({archive_link}).\n\n")

    # Walk sections in their original order rather than following `entries`, so a
    # section whose every item was archived still emits its heading and prose
    # instead of vanishing with its items. Falling back to entry order keeps the
    # function usable when no section map is supplied.
    by_h2 = {}
    for e in entries:
        by_h2.setdefault(e['h2'], []).append(e)

    ordered_h2 = list((sections or {}).keys())
    for e in entries:
        if e['h2'] not in ordered_h2:
            ordered_h2.append(e['h2'])

    for h2 in ordered_h2:
        section_entries = by_h2.get(h2, [])
        fallback = section_entries[0].get('section_prose', '') if section_entries else ''
        prose = sections.get(h2, fallback) if sections is not None else fallback
        if not section_entries:
            # Orphaned section: no surviving entry carries this prose.
            if not prose.strip():
                continue
            if not h2:
                continue
        if h2:
            header = h2 if h2.endswith('\n') else h2 + '\n'
            out.append(f"\n{header}")
            if prose.strip():
                out.append(prose if prose.endswith('\n') else prose + '\n')
            else:
                out.append('\n')
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
        active, preamble=preamble, archive_link=archive_basename, sections=sections
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
    # Archive first, and only truncate the source once the archive is durable.
    # Both go through a temp file + os.replace: two plain open(...,'w') calls leave
    # a window where an interruption truncates the source with its content not yet
    # anywhere else, and this script has no backup to fall back on.
    _atomic_write(archive_path, archive_text.strip() + '\n')
    _atomic_write(src_path, active_text.strip() + '\n')

    return stats

def _atomic_write(path: str, text: str) -> None:
    directory = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(dir=directory, prefix='.rotate-', suffix='.tmp')
    try:
        if os.path.exists(path):
            try:
                shutil.copymode(path, tmp)
            except OSError:
                pass
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        if hasattr(os, 'O_DIRECTORY'):
            try:
                dir_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
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
