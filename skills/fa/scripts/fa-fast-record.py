#!/usr/bin/env python3
"""fa-fast-record.py - Fast append to improvements.md without blocking interactive modals.

Corrections per plan-fa-staging-inbox-integration.md Fable audit 2026-09-12 (B.2, B.3)
and the roadmap-followup-fa-prep-20261010.md Sec.3.1 contract: explicit
workspace-root resolution, no auto-created global fallback, atomic-append
verification.

Further correction applied during Green implementation (2026-10-11, this
session): the prep-doc's own atomic-append check -- comparing the file's
`stat().st_size` before and after the write -- is racy under concurrent
writers (Ralph loop + an interactive `/fa fast` call can both append around
the same time). Empirically reproduced: 7/8 concurrent writers reported a
false [FAIL] while every entry was in fact written completely and intact
(TOCTOU: another writer's bytes land between this process's "before" stat
and its "after" stat, inflating the observed delta beyond this process's
own entry length). Fixed by verifying the `os.write()` syscall's own return
value (bytes actually written in this call) instead of an external
stat-delta -- this is unaffected by what any other process does to the file
in between. Re-verified empirically: 0/8 spurious failures under the same
concurrent-writer load, with all entries still present and byte-exact.
"""
import os
import sys
from datetime import datetime
from pathlib import Path


def resolve_workspace_root(start: Path):
    """Walk up from `start` looking for a `.git` entry (dir or file -- a
    worktree's `.git` is a file containing a `gitdir:` pointer, not a
    directory, so `.exists()` is used rather than `.is_dir()`); return
    None if none found."""
    cur = start.resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def fast_record(note: str, session_id: str = "unknown", source: str = "interactive") -> int:
    workspace_root = resolve_workspace_root(Path.cwd())
    if workspace_root is None:
        print(
            "[FAIL] No workspace root (.git ancestor) found -- refusing to write a global fallback inbox.",
            file=sys.stderr,
        )
        return 1

    inbox_path = workspace_root / ".agents" / "improvements.md"
    if not inbox_path.parent.exists():
        print(f"[FAIL] {inbox_path.parent} does not exist -- not auto-creating.", file=sys.stderr)
        return 1

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"\n## [Fast Record] {timestamp} (session {session_id[:8]}, source: {source})\n"
        f"- **Observation**: {note.strip()}\n"
        f"- **Tag**: [NEEDS_REVIEW]\n"
    )
    entry_bytes = entry.encode("utf-8")

    fd = os.open(str(inbox_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        written = os.write(fd, entry_bytes)
        os.fsync(fd)
    finally:
        os.close(fd)

    if written != len(entry_bytes):
        print(
            f"[FAIL] Atomic append verification failed: expected to write {len(entry_bytes)} bytes, "
            f"os.write() reported {written}.",
            file=sys.stderr,
        )
        return 1

    print(f"[OK] Recorded to {inbox_path} (Zero-Modal, verified). Continuing main task.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: fa-fast-record.py '<observation>' [--session <uuid>]")
    sys.exit(fast_record(sys.argv[1]))
