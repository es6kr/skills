#!/usr/bin/env python3
"""update_item.py — sanctioned `update` path for fix_plan.md / checklist.md.

`add_item.py` can add a brand-new schema-valid item, and `cleanup.py` can move
a fully-checked item into `## Completed`. Neither can mutate an EXISTING item
in place — flip its marker (e.g. `[ ]` -> `[BLOCKED:P1:external]`) or append a
one-line progress note — without going around `block-direct-checklist-edit.js`
via a raw Edit/Write. This closes that gap.

Matching: the single item whose action line contains --match (substring, on
the text after the marker) is mutated. 0 or 2+ matches is an error — the
error lists every candidate so the caller can narrow --match instead of
guessing which one was meant.

Usage:
  update_item.py --file <tracker> --match "<substring of the action text>"
                 [--set-marker "[x]"] [--append-note "..."] [--dry-run]
  update_item.py --test        # self-test, no tracker required

Exit codes: 0 = ok, 1 = validation/match failure, 2 = usage error.
"""

from __future__ import annotations

import argparse
try:
    import fcntl
except ImportError:
    fcntl = None
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add_item import validate_marker, atomic_write, MAX_BODY_LINES  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ITEM_RE = re.compile(r"^([ \t]*)-[ \t]+(\[[^\]]*\])[ \t]+(.*)$")


def find_item_block(lines: list[str], match_text: str) -> tuple[int, int, int]:
    """Locate the single item whose action text contains match_text.

    Returns (start, end, indent) where lines[start:end] is the item's own
    line plus every immediately-following more-indented sub-bullet line
    (its Why / How to apply / extra sub-bullets), stopping at the first
    blank line or line at same-or-shallower indentation.
    """
    candidates = [
        i for i, ln in enumerate(lines)
        if (m := ITEM_RE.match(ln)) and match_text in m.group(3)
    ]
    if len(candidates) == 0:
        raise ValueError(f"no item matched --match {match_text!r}")
    if len(candidates) > 1:
        previews = [lines[i].strip()[:80] for i in candidates]
        raise ValueError(
            f"{len(candidates)} items matched --match {match_text!r} — narrow it. "
            "Candidates: " + " | ".join(previews)
        )

    start = candidates[0]
    m = ITEM_RE.match(lines[start])
    assert m is not None
    indent = len(m.group(1))

    end = start + 1
    while end < len(lines):
        ln = lines[end]
        if not ln.strip():
            break
        line_indent = len(ln) - len(ln.lstrip(" \t"))
        if line_indent <= indent:
            break
        end += 1
    return start, end, indent


def apply_update(block: list[str], set_marker: str | None, append_note: str | None) -> list[str]:
    block = list(block)

    if set_marker:
        m = ITEM_RE.match(block[0])
        assert m is not None
        block[0] = f"{m.group(1)}- {set_marker} {m.group(3)}"

    if append_note:
        m = ITEM_RE.match(block[0])
        assert m is not None
        indent = len(m.group(1))
        note_line = " " * (indent + 2) + f"- {append_note.strip()}"
        prospective_len = len(block) + 1
        if prospective_len > MAX_BODY_LINES:
            raise ValueError(
                f"item body would grow to {prospective_len} lines, over the "
                f"{MAX_BODY_LINES}-line budget. Move the note into a "
                "research-<slug>.md / plan-<slug>.md artefact and reference it "
                "with a one-line sub-bullet instead (add.md 'Deliverable "
                "separation matrix')."
            )
        block.append(note_line)

    return block


def run_update(args: argparse.Namespace) -> int:
    if not args.set_marker and not args.append_note:
        raise ValueError("at least one of --set-marker / --append-note is required")
    if args.set_marker:
        validate_marker(args.set_marker)
    if args.append_note and ("\n" in args.append_note or "\r" in args.append_note):
        raise ValueError("--append-note must be a single line (no newlines)")

    if not os.path.exists(args.file):
        raise ValueError(f"tracker not found: {args.file}")

    with io.open(args.file, "r+", encoding="utf-8") as fh:
        try:
            if fcntl:
                fcntl.flock(fh, fcntl.LOCK_EX)
            src = fh.read()
        finally:
            if fcntl:
                fcntl.flock(fh, fcntl.LOCK_UN)

    lines = src.split("\n")
    start, end, _indent = find_item_block(lines, args.match)
    block = apply_update(lines[start:end], args.set_marker, args.append_note)

    out = "\n".join(lines[:start] + block + lines[end:])

    if args.dry_run:
        print("--- dry-run: item after update ---")
        print("\n".join(block))
        return 0

    atomic_write(args.file, out)
    print(f"OK: updated item matching --match {args.match!r} in {args.file}")
    print("\n".join(block))
    return 0


def self_test() -> int:
    passed = failed = 0

    def check(name: str, cond: bool) -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print(f"FAIL: {name}")

    doc_lines = [
        "# T",
        "",
        "## Priority Tasks",
        "",
        "- [ ] first item unique-marker-alpha",
        "  - **Why**: alpha reason",
        "  - **How to apply**: alpha steps",
        "",
        "- [ ] second item unique-marker-beta",
        "  - **Why**: beta reason",
        "  - **How to apply**: beta steps",
        "",
    ]

    # find_item_block: unique match
    start, end, indent = find_item_block(doc_lines, "unique-marker-alpha")
    check("finds unique match start", doc_lines[start].strip().startswith("- [ ] first item"))
    check("block includes Why/How sub-bullets", end - start == 3)
    check("indent detected as 0", indent == 0)

    # find_item_block: no match
    try:
        find_item_block(doc_lines, "nope-does-not-exist")
        check("no-match raises", False)
    except ValueError:
        check("no-match raises", True)

    # find_item_block: ambiguous match
    try:
        find_item_block(doc_lines, "item")
        check("ambiguous match raises", False)
    except ValueError as e:
        check("ambiguous match raises", True)
        check("ambiguous error lists both candidates", "first item" in str(e) and "second item" in str(e))

    # apply_update: set-marker only
    block = doc_lines[start:end]
    updated = apply_update(block, "[x]", None)
    check("set-marker rewrites the marker", updated[0].startswith("- [x] first item"))
    check("set-marker preserves action text", "unique-marker-alpha" in updated[0])
    check("set-marker leaves sub-bullets untouched", updated[1:] == block[1:])

    # apply_update: append-note only
    updated2 = apply_update(block, None, "progress note text")
    check("append-note grows block by one line", len(updated2) == len(block) + 1)
    check("append-note is indented 2 under item", updated2[-1] == "  - progress note text")
    check("append-note preserves original marker", updated2[0] == block[0])

    # apply_update: budget enforcement
    padded_block = block + [f"  - pad {i}" for i in range(7)]  # 3 + 7 = 10 lines, +1 note = 11 > 10
    try:
        apply_update(padded_block, None, "one more line pushes it over budget")
        check("length budget enforced", False)
    except ValueError:
        check("length budget enforced", True)

    # run_update end-to-end via a temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("\n".join(doc_lines))
        tmp_path = tf.name
    try:
        class NS:
            pass
        ns = NS()
        ns.file = tmp_path
        ns.match = "unique-marker-beta"
        ns.set_marker = "[x]"
        ns.append_note = "done via update_item"
        ns.dry_run = False
        rc = run_update(ns)
        check("run_update returns 0", rc == 0)
        with open(tmp_path, encoding="utf-8") as fh:
            result = fh.read()
        check("run_update wrote the new marker", "- [x] second item unique-marker-beta" in result)
        check("run_update wrote the note", "- done via update_item" in result)
        check("run_update left the other item untouched", "- [ ] first item unique-marker-alpha" in result)
    finally:
        os.unlink(tmp_path)

    # missing tracker file
    try:
        class NS2:
            pass
        ns2 = NS2()
        ns2.file = "/nonexistent/path/fix_plan.md"
        ns2.match = "x"
        ns2.set_marker = "[x]"
        ns2.append_note = None
        ns2.dry_run = False
        run_update(ns2)
        check("missing tracker raises", False)
    except ValueError:
        check("missing tracker raises", True)

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> int:
    p = argparse.ArgumentParser(
        description="Flip the marker on, or append a progress note to, an EXISTING fix_plan/checklist item"
    )
    p.add_argument("--test", action="store_true", help="run the self-test and exit")
    p.add_argument("--file", help="tracker path (fix_plan.md or checklist.md)")
    p.add_argument("--match", help="substring of the target item's action text (must match exactly one item)")
    p.add_argument("--set-marker", help="'[ ]', '[x]', '[-]', or '[BLOCKED:P<0-3>:external|selfable]'")
    p.add_argument("--append-note", help="one-line progress note appended as a new sub-bullet")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.test:
        return self_test()

    missing = [f for f in ("file", "match") if not getattr(args, f)]
    if missing:
        p.error("missing required argument(s): " + ", ".join("--" + m for m in missing))

    try:
        return run_update(args)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
