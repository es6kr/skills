#!/usr/bin/env python3
"""add_item.py — sanctioned `add` path for fix_plan.md / checklist.md.

`block-direct-checklist-edit.js` (PreToolUse:Edit/Write) blocks direct text edits
on these trackers and directs the caller to run a fix-plan script instead. The
scripts it names (detect_bloated_tasks / stale_check / cleanup) can all *inspect*
or *move* items, but none can **add** one — so the `add` topic had no sanctioned
path and callers were forced to hand-roll an insert. This closes that gap.

Enforces the `add` topic's schema (see add.md):
  - three required elements: Action / Why / How to apply
  - marker must be `[ ]`, `[x]`, or `[BLOCKED:P0-P3:external|selfable]`
  - length budget: 5-7 lines per item (verbose content belongs in artefacts)
  - refuses duplicates (idempotent — safe to re-run)

Usage:
  add_item.py --file <tracker> --action "..." --why "..." --how "..."
              [--section "## Priority Tasks"] [--marker "[ ]"]
              [--sub "**Research**: path/to/doc.md"]... [--position top|bottom]
              [--dry-run]
  add_item.py --test        # self-test, no tracker required

Exit codes: 0 = ok, 1 = validation failure, 2 = usage error.
"""

from __future__ import annotations

import argparse
import fcntl
import io
import os
import re
import sys
import tempfile

DEFAULT_TRACKER = "fix_plan.md"
DEFAULT_SECTION = "## Priority Tasks"
DEFAULT_MARKER = "[ ]"
MAX_BODY_LINES = 10  # 3 elements + up to 7 --sub entries (budget target 5-7, hard cap 10)


def validate_marker(marker: str) -> None:
    marker = marker.strip()
    if marker in ("[ ]", "[x]", "[-]"):
        return
    # [BLOCKED:P0-P3:external|selfable]
    if marker.startswith("[BLOCKED:") and marker.endswith("]"):
        parts = marker[len("[BLOCKED:") : -1].split(":")
        if len(parts) == 2:
            pri, kind = parts
            if pri in ("P0", "P1", "P2", "P3") and kind in ("external", "selfable"):
                return
    raise ValueError(
        f"invalid marker {marker!r}. Allowed: '[ ]', '[x]', '[-]', or '[BLOCKED:P0-P3:external|selfable]'"
    )


def validate_action(action: str) -> None:
    if not action or not action.strip():
        raise ValueError("--action must not be empty")
    if "\n" in action or "\r" in action:
        raise ValueError("--action must be a single line (no newlines)")
    if action.startswith(("- ", "* ", "1. ", "[")):
        raise ValueError(
            "--action must not include the list bullet or marker; pass the marker via --marker"
        )



def build_item(marker: str, action: str, why: str, how: str, subs: list[str] | None = None) -> str:
    """Assemble the item block. Why/How are mandatory (add.md three-element rule)."""
    subs = subs or []
    if not why.strip():
        raise ValueError("--why is required (future-session test: motivation in 1-2 sentences)")
    if not how.strip():
        raise ValueError("--how is required (procedure / tools / verification approach)")

    for name, val in [("--why", why), ("--how", how)]:
        if "\n" in val or "\r" in val:
            raise ValueError(f"{name} must not contain newline characters")
    for s in subs:
        if "\n" in s or "\r" in s:
            raise ValueError("--sub arguments must not contain newline characters")

    lines = [f"- {marker} {action.strip()}"]
    lines.append(f"  - **Why**: {why.strip()}")
    lines.append(f"  - **How to apply**: {how.strip()}")
    for s in subs:
        s = s.strip()
        if not s:
            continue
        lines.append(f"  - {s}")

    if len(lines) > MAX_BODY_LINES:
        raise ValueError(
            f"item body is {len(lines)} lines, over the {MAX_BODY_LINES}-line budget. "
            "Move diagnostics / option matrices / long context lists into a "
            "research-<slug>.md or plan-<slug>.md artefact and reference it with a "
            "one-line --sub instead (add.md 'Deliverable separation matrix')."
        )
    return "\n".join(lines)


def find_section(lines: list[str], section: str) -> int:
    """Return the index of the section heading line, or -1."""
    want = section.strip()
    for i, ln in enumerate(lines):
        if ln.strip() == want:
            return i
    return -1


def next_section_index(lines: list[str], start: int) -> int:
    """Index of the next top-level '## ' heading after `start`, else len(lines)."""
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            return i
    return len(lines)


def insert_item(text: str, section: str, item: str, position: str) -> str:
    lines = text.split("\n")
    idx = find_section(lines, section)
    if idx < 0:
        headings = [ln for ln in lines if ln.startswith("## ")]
        raise ValueError(
            f"section {section!r} not found. Available: {', '.join(headings) or '(none)'}"
        )

    if position == "top":
        at = idx + 1
        # skip blank lines directly under the heading
        while at < len(lines) and not lines[at].strip():
            at += 1
        block = item.split("\n") + [""]
    else:
        at = next_section_index(lines, idx)
        # back off over trailing blank lines so the item lands inside the section
        while at > idx + 1 and not lines[at - 1].strip():
            at -= 1
        block = [""] + item.split("\n")

    return "\n".join(lines[:at] + block + lines[at:])


def atomic_write(path: str, text: str) -> None:
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".add_item.", suffix=".tmp")
    try:
        with io.open(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def run_add(args: argparse.Namespace) -> int:
    validate_marker(args.marker)
    validate_action(args.action)

    if args.section.strip() == "## Completed" and args.marker.strip() in ("[ ]", "[-]"):
        print("ERROR: cannot add active items to '## Completed' section", file=sys.stderr)
        return 1

    try:
        item = build_item(args.marker, args.action, args.why, args.how, args.sub or [])
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if not os.path.exists(args.file):
        print(f"ERROR: tracker not found: {args.file}", file=sys.stderr)
        return 1

    escaped_action = re.escape(args.action.strip())
    pattern = re.compile(rf"^[ \t]*-[ \t]+\[[ x/X-]\][ \t]+{escaped_action}(?:[ \t]|$)", re.MULTILINE)

    with io.open(args.file, "r+", encoding="utf-8") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX)
            src = fh.read()
            if pattern.search(src):
                print(f"SKIP: an item with this action already exists in {args.file} (idempotent no-op)")
                return 0

            out = insert_item(src, args.section, item, args.position)

            if args.dry_run:
                print("--- dry-run: item that would be inserted ---")
                print(item)
                print(f"--- into section {args.section!r} at {args.position} ---")
                return 0

            atomic_write(args.file, out)
            print(f"OK: added to {args.section!r} in {args.file} (+{len(out) - len(src)} chars)")
            print(item)
            return 0
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def self_test() -> int:
    passed = failed = 0

    def check(name: str, cond: bool) -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print(f"FAIL: {name}")

    # marker validation
    for good in ("[ ]", "[x]", "[BLOCKED:P0:external]", "[BLOCKED:P3:selfable]"):
        try:
            validate_marker(good)
            check(f"marker accepts {good}", True)
        except ValueError:
            check(f"marker accepts {good}", False)
    for bad in ("[]", "[BLOCKED]", "[BLOCKED:P4:external]", "[BLOCKED:P1:other]", "[ x ]"):
        try:
            validate_marker(bad)
            check(f"marker rejects {bad}", False)
        except ValueError:
            check(f"marker rejects {bad}", True)

    # three-element rule
    try:
        build_item("[ ]", "do a thing", "", "steps")
        check("missing --why rejected", False)
    except ValueError:
        check("missing --why rejected", True)
    try:
        build_item("[ ]", "do a thing", "because", "")
        check("missing --how rejected", False)
    except ValueError:
        check("missing --how rejected", True)

    # length budget
    try:
        build_item("[ ]", "a", "b", "c", [f"sub {i}" for i in range(10)])
        check("length budget enforced", False)
    except ValueError:
        check("length budget enforced", True)

    # action shape
    for bad in ("- already bulleted", "[ ] already marked", "", "two\nlines"):
        try:
            validate_action(bad)
            check(f"action rejects {bad!r}", False)
        except ValueError:
            check(f"action rejects {bad!r}", True)

    # insertion, top and bottom
    doc = "# T\n\n## Progress\n\n- [ ] existing\n\n## Completed\n\n- done\n"
    item = build_item("[ ]", "new thing", "why text", "how text")
    top = insert_item(doc, "## Progress", item, "top")
    check("top insert lands before existing", top.index("new thing") < top.index("existing"))
    check("top insert stays in Progress", top.index("new thing") < top.index("## Completed"))
    bot = insert_item(doc, "## Progress", item, "bottom")
    check("bottom insert lands after existing", bot.index("new thing") > bot.index("existing"))
    check("bottom insert stays in Progress", bot.index("new thing") < bot.index("## Completed"))
    check("other sections untouched", "## Completed\n\n- done" in bot)

    # missing section
    try:
        insert_item(doc, "## Nope", item, "top")
        check("missing section rejected", False)
    except ValueError:
        check("missing section rejected", True)

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Add a schema-valid item to fix_plan.md / checklist.md")
    p.add_argument("--test", action="store_true", help="run the self-test and exit")
    p.add_argument("--file", help="tracker path (fix_plan.md or checklist.md)")
    p.add_argument("--action", help="one-sentence imperative action (no bullet, no marker)")
    p.add_argument("--why", help="motivation, 1-2 sentences (required)")
    p.add_argument("--how", help="procedure / tools / verification (required)")
    p.add_argument("--sub", action="append", default=[], help="extra one-line sub-bullet (repeatable)")
    p.add_argument("--section", default="## Priority Tasks", help="target section heading")
    p.add_argument("--marker", default="[ ]", help="'[ ]', '[x]', or '[BLOCKED:P<0-3>:external|selfable]'")
    p.add_argument("--position", choices=("top", "bottom"), default="top")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.test:
        return self_test()

    missing = [f for f in ("file", "action", "why", "how") if not getattr(args, f)]
    if missing:
        p.error("missing required argument(s): " + ", ".join("--" + m for m in missing))

    try:
        return run_add(args)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
