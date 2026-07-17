#!/usr/bin/env python3
"""Trim memory-index hook lines to a per-line byte cap.

A Claude Code project memory index (MEMORY.md) holds one pointer line per
memory file: `- [Title](file.md) — hook`. The index is loaded into context
every session, so it carries a byte budget. This script shortens oversized
hook text at a clause boundary — but only when the linked memory file exists
and is large enough to plausibly hold the detail (the hook is a recall cue,
not the storage medium).

Only link-pointer lines are touched. Inline-content bullets, headers, and
tables are left alone (relocate those to memory files manually). Merging or
deleting stale entries is out of scope — that needs user approval.

Usage:
  python trim-memory-index.py MEMORY.md [--budget 17100] [--line-cap 160]
      [--min-file-bytes 300] [--dry-run] [--no-backup]

Exit codes: 0 = under budget after trim, 1 = still over budget, 2 = usage error.
"""

import argparse
import io
import os
import re
import sys

LINK_LINE = re.compile(r"^(- \[[^\]]+\]\(([^)]+)\) — )(.*)$")
# Clause separators, in no particular order — the rightmost match within the
# byte budget wins so the cut lands on a natural boundary.
SEPARATORS = [". ", " — ", ", ", " (", "·", " + ", " / "]


def cut_at_boundary(hook: str, avail: int) -> str:
    """Cut hook text to <= avail bytes at the best clause boundary."""
    raw = hook.encode("utf-8")[:avail]
    while True:
        try:
            cand = raw.decode("utf-8")
            break
        except UnicodeDecodeError:
            raw = raw[:-1]
    best = max(cand.rfind(sep) for sep in SEPARATORS)
    cut = cand[:best] if best >= 40 else cand.rsplit(" ", 1)[0]
    cut = cut.rstrip(" ,;·—-(")
    if cut.count("`") % 2:  # never leave an unbalanced inline-code span
        cut = cut.rsplit("`", 1)[0].rstrip(" ,;·—-(")
    return cut


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("memory_md", help="path to the memory index (MEMORY.md)")
    ap.add_argument("--budget", type=int, default=17100,
                    help="total byte budget for the index (default: 17100)")
    ap.add_argument("--line-cap", type=int, default=160,
                    help="per-line byte cap for link-pointer lines (default: 160)")
    ap.add_argument("--min-file-bytes", type=int, default=300,
                    help="skip trimming when the linked file is smaller than this "
                         "(detail may not be preserved there; default: 300)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change without writing")
    ap.add_argument("--no-backup", action="store_true",
                    help="skip writing <file>.bak-trim before modifying")
    args = ap.parse_args()

    path = args.memory_md
    if not os.path.isfile(path):
        print(f"error: not a file: {path}", file=sys.stderr)
        return 2
    mdir = os.path.dirname(os.path.abspath(path))

    lines = io.open(path, encoding="utf-8").readlines()
    before = sum(len(l.encode("utf-8")) for l in lines)

    out = []
    trimmed = skipped = 0
    for line in lines:
        m = LINK_LINE.match(line.rstrip("\n"))
        if not m or len(line.encode("utf-8")) <= args.line_cap + 1:
            out.append(line)
            continue
        target = os.path.join(mdir, m.group(2))
        if not (os.path.isfile(target) and os.path.getsize(target) >= args.min_file_bytes):
            skipped += 1  # detail not guaranteed in the file — leave the hook intact
            out.append(line)
            continue
        head, hook = m.group(1), m.group(3)
        avail = args.line_cap - len(head.encode("utf-8"))
        if avail < 30:
            skipped += 1
            out.append(line)
            continue
        out.append(head + cut_at_boundary(hook, avail) + "\n")
        trimmed += 1

    after = sum(len(l.encode("utf-8")) for l in out)
    print(f"lines: {len(lines)} | trimmed: {trimmed} | skipped (target too small/missing): {skipped}")
    print(f"bytes: {before} -> {after} (budget {args.budget})")

    if not args.dry_run and trimmed:
        if not args.no_backup:
            bak = path + ".bak-trim"
            io.open(bak, "w", encoding="utf-8", newline="").writelines(lines)
            print(f"backup: {bak}")
        io.open(path, "w", encoding="utf-8", newline="").writelines(out)

    if after > args.budget:
        print("still over budget — relocate inline-content bullets into memory "
              "files, or review stale entries (user approval required).",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
