#!/usr/bin/env python3
"""claim_item.py — sanctioned `claim` path for fix_plan.md / checklist.md.

`block-direct-checklist-edit.js` (PreToolUse:Edit/Write) blocks direct text
edits on these trackers and directs the caller to run a fix-plan script
instead. `add_item.py` closed the "add" gap; this closes the "claim" gap
documented in claim.md but never given a sanctioned script -- stamping,
refreshing, taking over, and releasing a `[CLAIMED:<sid>:<ts>]` lease tag
were all only possible via an ad hoc one-off edit.

Usage:
  claim_item.py claim   --file <tracker> --action "..." --sid <8hex> --now <YYYY-MM-DDTHH:mm> [--ttl-hours 4]
  claim_item.py release --file <tracker> --action "..." --sid <8hex>
  claim_item.py --test   # self-test, no tracker required

Exit codes: 0 = ok, 1 = rejected (see stderr), 2 = usage error.

This module does not read the system clock (`--now` is caller-supplied) --
same convention as cleanup.py's caller-supplied `--cutoff`.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import tempfile
from datetime import datetime

DEFAULT_TTL_HOURS = 4

# Matches: "- [marker] [CLAIMED:sid:ts] action text" (the CLAIMED group is optional).
# marker is one of: [ ] / [x] / [-] / [BLOCKED:P0-3:external|selfable].
ITEM_RE = re.compile(
    r"^(?P<indent>\s*)-\s+(?P<marker>\[(?:[ x\-]|BLOCKED:P[0-3]:(?:external|selfable))\])"
    r"(?:\s+\[CLAIMED:(?P<sid>[0-9a-f]{6,40}):(?P<ts>[^\]]+)\])?"
    r"\s+(?P<action>.+)$"
)

CLAIMABLE_MARKERS = re.compile(r"^\[(?: |BLOCKED:P[0-3]:selfable)\]$")


def is_stale(ts_str: str, now: str, ttl_hours: int = DEFAULT_TTL_HOURS) -> bool:
    """A claim is stale when its timestamp is older than ttl_hours relative to now."""
    ts = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M")
    now_dt = datetime.strptime(now, "%Y-%m-%dT%H:%M")
    age_hours = (now_dt - ts).total_seconds() / 3600
    return age_hours > ttl_hours


def _find_item(lines: list[str], action: str):
    """Return (index, match) for the first line whose action text matches, or (None, None)."""
    target = action.strip()
    for i, line in enumerate(lines):
        m = ITEM_RE.match(line)
        if m and m.group("action").strip() == target:
            return i, m
    return None, None


def _write_lines(path, lines: list[str], had_trailing_newline: bool) -> None:
    content = "\n".join(lines)
    if had_trailing_newline:
        content += "\n"
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".claim_item.", suffix=".tmp")
    try:
        with io.open(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def claim(path, action: str, sid: str, now: str, ttl_hours: int = DEFAULT_TTL_HOURS) -> dict:
    """Stamp, refresh, or take over a [CLAIMED:sid:ts] lease tag on the item
    matching `action`. Only `[ ]` and `[BLOCKED:P*:selfable]` items are
    claimable (claim.md: "never stamp a claim on [x] ... or [BLOCKED:*:external]")."""
    if not os.path.exists(path):
        return {"ok": False, "error": f"tracker not found: {path}"}

    with io.open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    had_trailing_newline = raw.endswith("\n")
    lines = raw.split("\n")
    if had_trailing_newline and lines and lines[-1] == "":
        lines.pop()

    idx, m = _find_item(lines, action)
    if idx is None:
        return {"ok": False, "error": f"action not found in tracker: {action!r}"}

    marker = m.group("marker")
    if not CLAIMABLE_MARKERS.match(marker):
        return {
            "ok": False,
            "error": f"cannot claim item with marker {marker} "
            "(only [ ] and [BLOCKED:P*:selfable] are claimable; "
            "external and completed items are not progressable now)",
        }

    existing_sid = m.group("sid")
    existing_ts = m.group("ts")
    if existing_sid is not None and existing_sid != sid:
        if not is_stale(existing_ts, now, ttl_hours):
            return {
                "ok": False,
                "error": f"in flight: claimed by session {existing_sid} at {existing_ts} "
                f"(fresh, within {ttl_hours}h TTL) — pick a different item or report the conflict",
            }
        # Stale — takeover falls through to the same stamp logic below.

    new_line = (
        f"{m.group('indent')}- {marker} [CLAIMED:{sid}:{now}] {m.group('action')}"
    )
    lines[idx] = new_line
    _write_lines(path, lines, had_trailing_newline)
    return {"ok": True, "line": new_line}


def release(path, action: str, sid: str) -> dict:
    """Remove the [CLAIMED:...] tag from the item matching `action`, if it is
    this session's own claim. A no-op (ok:True) when the item carries no
    claim tag at all. Rejects releasing another live session's claim."""
    if not os.path.exists(path):
        return {"ok": False, "error": f"tracker not found: {path}"}

    with io.open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    had_trailing_newline = raw.endswith("\n")
    lines = raw.split("\n")
    if had_trailing_newline and lines and lines[-1] == "":
        lines.pop()

    idx, m = _find_item(lines, action)
    if idx is None:
        return {"ok": False, "error": f"action not found in tracker: {action!r}"}

    existing_sid = m.group("sid")
    if existing_sid is None:
        return {"ok": True, "line": lines[idx]}
    if existing_sid != sid:
        return {
            "ok": False,
            "error": f"cannot release: claimed by a different session ({existing_sid})",
        }

    new_line = f"{m.group('indent')}- {m.group('marker')} {m.group('action')}"
    lines[idx] = new_line
    _write_lines(path, lines, had_trailing_newline)
    return {"ok": True, "line": new_line}


def self_test() -> int:
    passed = failed = 0

    def check(name: str, cond: bool) -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print(f"FAIL: {name}")

    check("is_stale true past ttl", is_stale("2026-08-26T06:00", "2026-08-26T12:30", 4))
    check("is_stale false within ttl", not is_stale("2026-08-26T10:00", "2026-08-26T12:30", 4))
    check("claimable marker [ ]", bool(CLAIMABLE_MARKERS.match("[ ]")))
    check("claimable marker selfable", bool(CLAIMABLE_MARKERS.match("[BLOCKED:P0:selfable]")))
    check("not claimable [x]", not CLAIMABLE_MARKERS.match("[x]"))
    check("not claimable external", not CLAIMABLE_MARKERS.match("[BLOCKED:P0:external]"))

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Stamp/refresh/takeover/release a [CLAIMED:...] lease tag")
    p.add_argument("--test", action="store_true", help="run the self-test and exit")
    sub = p.add_subparsers(dest="command")

    claim_p = sub.add_parser("claim")
    claim_p.add_argument("--file", required=False)
    claim_p.add_argument("--action", required=False)
    claim_p.add_argument("--sid", required=False, help="8-char session id prefix")
    claim_p.add_argument("--now", required=False, help="YYYY-MM-DDTHH:mm (caller-supplied, not read from the clock)")
    claim_p.add_argument("--ttl-hours", type=int, default=DEFAULT_TTL_HOURS)

    release_p = sub.add_parser("release")
    release_p.add_argument("--file", required=False)
    release_p.add_argument("--action", required=False)
    release_p.add_argument("--sid", required=False)

    args = p.parse_args()

    if args.test:
        return self_test()

    if args.command == "claim":
        missing = [f for f in ("file", "action", "sid", "now") if not getattr(args, f)]
        if missing:
            p.error("claim: missing required argument(s): " + ", ".join("--" + m for m in missing))
        result = claim(args.file, args.action, args.sid, args.now, args.ttl_hours)
    elif args.command == "release":
        missing = [f for f in ("file", "action", "sid") if not getattr(args, f)]
        if missing:
            p.error("release: missing required argument(s): " + ", ".join("--" + m for m in missing))
        result = release(args.file, args.action, args.sid)
    else:
        p.error("a command is required: claim | release (or --test)")
        return 2

    if result["ok"]:
        print(f"OK: {result['line']}")
        return 0
    print(f"ERROR: {result['error']}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
