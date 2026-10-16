#!/usr/bin/env python3
"""tracker_id.py — tracker ID uniqueness checker and sequence resolver for fix-plan.

Provides utilities to scan markdown trackers (e.g. fix_plan.md, checklist.md)
for used project-prefixed sequence IDs (e.g. `[AIAUTO-12]`), verify uniqueness,
and resolve next available sequence numbers upon collision.

Usage:
  python3 tracker_id.py --file <path> --prefix <PREFIX> [--seq <N>] [--json]
"""

import argparse
import json
import os
import re
import sys

# Pattern matching tracker items with project identifiers:
# - [ ] [AIAUTO-12] ...
# - [x] [INFRA-3] ...
# - [BLOCKED:P2:selfable] [DTWEB-10] ...
TRACKER_ID_RE = re.compile(r"^[ \t]*-[ \t]+\[[^\]]*\][ \t]+\[([A-Za-z0-9_]+)-(\d+)\]")


def scan_used_sequences(tracker_path: str, prefix: str) -> set[int]:
    """Scan a tracker markdown file and return a set of integer sequence IDs used by prefix.

    Args:
        tracker_path: Path to the markdown tracker file.
        prefix: Project prefix code (e.g. "AIAUTO", "ES6KR", "INFRA"). Case-insensitive.

    Returns:
        Set of integer sequence numbers already assigned under that prefix.
    """
    clean_prefix = prefix.strip().rstrip("-").upper()
    used: set[int] = set()

    if not tracker_path or not os.path.exists(tracker_path):
        return used

    with open(tracker_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = TRACKER_ID_RE.match(line)
            if m:
                item_prefix = m.group(1).upper()
                if item_prefix == clean_prefix:
                    try:
                        seq = int(m.group(2))
                        used.add(seq)
                    except ValueError:
                        pass
    return used


def get_next_available_id(
    tracker_path: str, prefix: str, requested_seq: int | None = None
) -> tuple[str, bool]:
    """Resolve the next available tracker ID for a prefix, avoiding collisions.

    If requested_seq is provided and free, it is assigned.
    If requested_seq is provided and already taken, increments sequentially
    to the next free integer, setting collided=True.
    If requested_seq is not provided, defaults to max(used) + 1 (or 1 if none).

    Args:
        tracker_path: Path to the markdown tracker file.
        prefix: Project prefix code (e.g. "AIAUTO").
        requested_seq: Optional desired sequence number.

    Returns:
        A tuple of (assigned_identifier_string, collided_boolean).
        Example: ("AIAUTO-3", False) or ("AIAUTO-4", True)
    """
    clean_prefix = prefix.strip().rstrip("-").upper()
    used_seqs = scan_used_sequences(tracker_path, clean_prefix)

    if requested_seq is not None:
        start_seq = requested_seq
    else:
        start_seq = (max(used_seqs) + 1) if used_seqs else 1

    seq = start_seq
    while seq in used_seqs:
        seq += 1

    collided = (requested_seq is not None) and (seq != requested_seq)
    assigned_id = f"{clean_prefix}-{seq}"
    return assigned_id, collided


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify tracker ID uniqueness and resolve next available sequence."
    )
    parser.add_argument("--file", "-f", required=True, help="Path to tracker markdown file")
    parser.add_argument("--prefix", "-p", required=True, help="Project prefix (e.g. AIAUTO, ES6KR)")
    parser.add_argument("--seq", "-s", type=int, default=None, help="Desired sequence number")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")

    args = parser.parse_args(argv)

    assigned_id, collided = get_next_available_id(
        tracker_path=args.file, prefix=args.prefix, requested_seq=args.seq
    )

    if args.json:
        res = {
            "identifier": assigned_id,
            "prefix": args.prefix.strip().rstrip("-").upper(),
            "requested_seq": args.seq,
            "collided": collided,
            "tracker_file": args.file,
        }
        print(json.dumps(res, indent=2))
    else:
        if collided:
            print(f"COLLISION: Requested {args.prefix.upper()}-{args.seq} is already in use.")
            print(f"Assigned next available ID: {assigned_id}")
        else:
            print(f"Available ID: {assigned_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
