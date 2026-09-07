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
import time
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(_SCRIPT_DIR))
# plane_sync lives in the backlog skill's scripts/ since the plane->backlog migration.
sys.path.insert(0, str(_SCRIPT_DIR.parent.parent / "backlog" / "scripts"))
import plane_sync  # noqa: E402 -- needs sys.path adjusted first (backlog skill script)

DEFAULT_TTL_HOURS = 4

# Matches: "- [marker] [CLAIMED:sid:ts] action text" (the CLAIMED group is optional).
# marker is one of: [ ] / [x] / [-] / [BLOCKED:P0-3:external|selfable].
ITEM_RE = re.compile(
    r"^(?P<indent>\s*)-\s+(?P<marker>\[(?:[ x\-]|BLOCKED:P[0-3]:(?:external|selfable))\])"
    r"(?:\s+\[CLAIMED:(?P<sid>[0-9a-f]{6,40}):(?P<ts>[^\]]+)\])?"
    r"\s+(?P<action>.+)$"
)

CLAIMABLE_MARKERS = re.compile(r"^\[(?: |BLOCKED:P[0-3]:selfable)\]$")

TS_FORMAT = "%Y-%m-%dT%H:%M"
# Must agree with ITEM_RE's CLAIMED group: a sid outside this charset produces a
# tag ITEM_RE can never re-match, which strands the item on the sanctioned path.
SID_RE = re.compile(r"^[0-9a-f]{6,40}$")

# How long to wait for the tracker lock before giving up, and the poll interval.
LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_SECONDS = 0.05


def validate_sid(sid) -> str | None:
    """Return an error string when `sid` is not a usable session-id prefix."""
    if not isinstance(sid, str) or not SID_RE.match(sid):
        return (
            f"invalid sid {sid!r}: expected 6-40 lowercase hex characters "
            "(claim.md uses an 8-char session-id prefix). A sid outside that "
            "charset writes a tag this script can never find again."
        )
    return None


def validate_timestamp(value, label: str) -> str | None:
    """Return an error string when `value` is not a `YYYY-MM-DDTHH:mm` stamp."""
    try:
        datetime.strptime(value, TS_FORMAT)
    except (TypeError, ValueError):
        return f"invalid {label} {value!r}: expected {TS_FORMAT} (e.g. 2026-08-26T12:34)"
    return None


class _TrackerLock:
    """Advisory exclusive lock around a whole read-validate-write transaction.

    `os.replace` makes the final swap atomic but does NOT serialize the
    read-validate-write sequence: two claimers can both read the same
    snapshot and the later replace silently discards the earlier lease
    mutation. A sidecar lock file created with O_CREAT|O_EXCL closes that
    window and -- unlike fcntl -- works on native Windows Python, which this
    module deliberately supports.
    """

    def __init__(self, path, timeout: float = LOCK_TIMEOUT_SECONDS):
        self.lock_path = os.path.abspath(path) + ".lock"
        self.timeout = timeout

    def __enter__(self):
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"could not acquire tracker lock within {self.timeout}s: "
                        f"{self.lock_path} (another session may be mid-write; "
                        "remove the lock file if no other session is running)"
                    )
                time.sleep(LOCK_POLL_SECONDS)

    def __exit__(self, *exc_info):
        try:
            os.unlink(self.lock_path)
        except FileNotFoundError:
            pass
        return False


def is_stale(ts_str: str, now: str, ttl_hours: int = DEFAULT_TTL_HOURS) -> bool:
    """A claim is stale when its timestamp is older than ttl_hours relative to now."""
    ts = datetime.strptime(ts_str, TS_FORMAT)
    now_dt = datetime.strptime(now, TS_FORMAT)
    age_hours = (now_dt - ts).total_seconds() / 3600
    return age_hours > ttl_hours


def _find_all_items(lines: list[str], action: str) -> list[tuple[int, re.Match]]:
    """Return every (index, match) whose action text equals `action`."""
    target = action.strip()
    found = []
    for i, line in enumerate(lines):
        m = ITEM_RE.match(line)
        if m and m.group("action").strip() == target:
            found.append((i, m))
    return found


def _find_item(lines: list[str], action: str):
    """Return (index, match) for the first line whose action text matches, or (None, None)."""
    matches = _find_all_items(lines, action)
    return matches[0] if matches else (None, None)


def _select_item(lines: list[str], action: str, prefer):
    """Resolve `action` to exactly one item.

    Returns (index, match, error). Matching the FIRST line unconditionally is
    unsafe for a coordination lease: a duplicated action text silently
    misroutes the claim, and a completed copy appearing above an open one
    produces a bogus "cannot claim [x]" rejection. `prefer` narrows a
    multi-match set to the lines that are actually actionable; only a genuine
    ambiguity is rejected.
    """
    matches = _find_all_items(lines, action)
    if not matches:
        return None, None, f"action not found in tracker: {action!r}"
    if len(matches) == 1:
        return matches[0][0], matches[0][1], None

    preferred = [(i, m) for i, m in matches if prefer(m)]
    if len(preferred) == 1:
        return preferred[0][0], preferred[0][1], None

    candidates = preferred if preferred else matches
    line_nos = ", ".join(str(i + 1) for i, _ in candidates)
    return None, None, (
        f"ambiguous action: {len(candidates)} tracker lines match {action!r} "
        f"(lines {line_nos}). Disambiguate the action text before claiming -- "
        "a lease stamped on the wrong duplicate is invisible to the other session."
    )


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


def _push_claim_to_plane(action: str, plane_profile: dict) -> dict | None:
    """If `action` is also a Plane index line (`[IDENT-N] title -> Plane
    (url)`), push the claim through by transitioning the linked issue to the
    started-group state. Returns None when the line isn't a Plane index line
    (nothing to push); otherwise the transition_issue_to_started() result."""
    url_match = plane_sync.PLANE_URL_RE.search(action)
    if not url_match:
        return None
    result = plane_sync.transition_issue_to_started(
        plane_profile, url_match["workspace"], url_match["project"], url_match["issue"]
    )
    return {"ok": "error" not in result, **result}


def claim(
    path, action: str, sid: str, now: str, ttl_hours: int = DEFAULT_TTL_HOURS,
    plane_profile: dict | None = None,
) -> dict:
    """Stamp, refresh, or take over a [CLAIMED:sid:ts] lease tag on the item
    matching `action`. Only `[ ]` and `[BLOCKED:P*:selfable]` items are
    claimable (claim.md: "never stamp a claim on [x] ... or [BLOCKED:*:external]").

    When `plane_profile` is supplied and the claimed line is also a Plane
    index line, the linked Plane issue is transitioned to its started-group
    state (see plane_sync.transition_issue_to_started()) so the claim is
    reflected on the Plane side too, not just in the local tracker. A Plane
    API failure is surfaced via the returned `plane_sync` key but never fails
    the (already-applied) local claim -- the local write is the source of
    truth; Plane is a best-effort mirror."""
    # Reject-before-mutate: every input is validated before the tracker is
    # opened, so a bad argument can never leave a half-formed lease behind.
    for err in (
        validate_sid(sid),
        validate_timestamp(now, "now"),
        None if isinstance(ttl_hours, int) and not isinstance(ttl_hours, bool) and ttl_hours > 0
        else f"invalid ttl_hours {ttl_hours!r}: expected a positive integer "
             "(a non-positive TTL marks every live claim stale and allows instant takeover)",
    ):
        if err:
            return {"ok": False, "error": err}

    if not os.path.exists(path):
        return {"ok": False, "error": f"tracker not found: {path}"}

    try:
        with _TrackerLock(path):
            result, plane_action = _claim_locked(path, action, sid, now, ttl_hours)
    except TimeoutError as exc:
        return {"ok": False, "error": str(exc)}

    if not result["ok"] or plane_profile is None or plane_action is None:
        return result

    # The local write already succeeded. Plane is a best-effort mirror, so no
    # failure here -- including an unexpected one from a malformed profile or
    # an unexpected response shape -- may turn the applied claim into an error.
    try:
        plane_result = _push_claim_to_plane(plane_action, plane_profile)
    except Exception as exc:
        result["plane_sync"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    else:
        if plane_result is not None:
            result["plane_sync"] = plane_result
    return result


def _claim_locked(path, action: str, sid: str, now: str, ttl_hours: int):
    """The read-validate-write half of claim(), executed under the tracker lock.

    Returns (result, plane_action); `plane_action` is the matched action text
    to mirror to Plane, or None when nothing should be mirrored.
    """
    with io.open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    had_trailing_newline = raw.endswith("\n")
    lines = raw.split("\n")
    if had_trailing_newline and lines and lines[-1] == "":
        lines.pop()

    idx, m, err = _select_item(
        lines, action, prefer=lambda mt: bool(CLAIMABLE_MARKERS.match(mt.group("marker")))
    )
    if err:
        return {"ok": False, "error": err}, None

    marker = m.group("marker")
    if not CLAIMABLE_MARKERS.match(marker):
        return {
            "ok": False,
            "error": f"cannot claim item with marker {marker} "
            "(only [ ] and [BLOCKED:P*:selfable] are claimable; "
            "external and completed items are not progressable now)",
        }, None

    existing_sid = m.group("sid")
    existing_ts = m.group("ts")
    if existing_sid is not None and existing_sid != sid:
        ts_err = validate_timestamp(existing_ts, "stored claim timestamp")
        if ts_err:
            # A corrupted tag must surface as the documented structured error,
            # not as a ValueError traceback out of the CLI.
            return {
                "ok": False,
                "error": f"{ts_err} -- the tracker line for {action!r} carries a "
                         "corrupt [CLAIMED:...] tag and needs manual repair",
            }, None
        if not is_stale(existing_ts, now, ttl_hours):
            return {
                "ok": False,
                "error": f"in flight: claimed by session {existing_sid} at {existing_ts} "
                f"(fresh, within {ttl_hours}h TTL) — pick a different item or report the conflict",
            }, None
        # Stale — takeover falls through to the same stamp logic below.

    new_line = (
        f"{m.group('indent')}- {marker} [CLAIMED:{sid}:{now}] {m.group('action')}"
    )
    lines[idx] = new_line
    _write_lines(path, lines, had_trailing_newline)

    return {"ok": True, "line": new_line}, m.group("action")


def release(path, action: str, sid: str) -> dict:
    """Remove the [CLAIMED:...] tag from the item matching `action`, if it is
    this session's own claim. A no-op (ok:True) when the item carries no
    claim tag at all. Rejects releasing another live session's claim.

    Release is local-only: it does NOT reverse the Plane started-transition
    that `claim(--plane-sync)` applied. That is deliberate -- a released item
    is usually still in progress for whoever picks it up next, so demoting the
    linked Plane issue would misreport the board. Move the Plane issue back by
    hand if a release really does mean "no longer started"."""
    sid_err = validate_sid(sid)
    if sid_err:
        return {"ok": False, "error": sid_err}

    if not os.path.exists(path):
        return {"ok": False, "error": f"tracker not found: {path}"}

    try:
        with _TrackerLock(path):
            return _release_locked(path, action, sid)
    except TimeoutError as exc:
        return {"ok": False, "error": str(exc)}


def _release_locked(path, action: str, sid: str) -> dict:
    """The read-validate-write half of release(), executed under the tracker lock."""
    with io.open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    had_trailing_newline = raw.endswith("\n")
    lines = raw.split("\n")
    if had_trailing_newline and lines and lines[-1] == "":
        lines.pop()

    idx, m, err = _select_item(
        lines, action, prefer=lambda mt: mt.group("sid") == sid
    )
    if err:
        return {"ok": False, "error": err}

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
    claim_p.add_argument(
        "--plane-sync", action="store_true",
        help="also transition the linked Plane issue (if the claimed line is a "
        "Plane index line) to its started-group state -- opt-in, off by default",
    )
    claim_p.add_argument("--plane-workspace", help="workspace profile override for --plane-sync")

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
        plane_profile = None
        if args.plane_sync:
            from workspace_profile import get_profile
            plane_profile = get_profile(workspace_name=args.plane_workspace, target_path=args.file)
        result = claim(args.file, args.action, args.sid, args.now, args.ttl_hours, plane_profile)
    elif args.command == "release":
        missing = [f for f in ("file", "action", "sid") if not getattr(args, f)]
        if missing:
            p.error("release: missing required argument(s): " + ", ".join("--" + m for m in missing))
        result = release(args.file, args.action, args.sid)
    else:
        p.error("a command is required: claim | release (or --test)")
        return 2

    if not result["ok"]:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        return 1
    print(f"OK: {result['line']}")
    plane_result = result.get("plane_sync")
    if plane_result is not None:
        if plane_result["ok"]:
            print("[Plane Sync] issue transitioned to started")
        else:
            print(f"[Plane Sync] failed (local claim unaffected): {plane_result.get('error')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
