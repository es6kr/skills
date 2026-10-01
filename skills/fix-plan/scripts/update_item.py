#!/usr/bin/env python3
"""update_item.py — sanctioned `update` path for fix_plan.md / checklist.md.

`add_item.py` can add a brand-new schema-valid item, and `cleanup.py` archives
entries that are already inside `## Completed` by date cutoff. Neither can
mutate an EXISTING item in place — flip its marker (e.g. `[ ]` ->
`[BLOCKED:P1:external]`), append a one-line progress note, or move a finished
item out of an active section into `## Completed` — without going around
`block-direct-checklist-edit.js` via a raw Edit/Write. This closes that gap.

Matching: the single item whose action line contains --match (substring, on
the text after the marker) is mutated. 0 or 2+ matches is an error — the
error lists every candidate so the caller can narrow --match instead of
guessing which one was meant.

Usage:
  update_item.py --file <tracker> --match "<substring of the action text>"
                 [--set-marker "[x]"] [--append-note "..."] [--dry-run]
  update_item.py --file <tracker> --match "<substring>" --move
                 [--summary "one-line condensed text"] [--dry-run]
  update_item.py --file <tracker> --match "<substring>" --delete [--dry-run]
  update_item.py --test        # self-test, no tracker required

--move performs a MECHANICAL (non-semantic) version of the fix-plan skill's
"Move" step (see move.md): it deletes the matched item's entire block (its
own line plus every sub-bullet) from wherever it currently sits, and inserts
a single-line, marker-free entry at the top of `## Completed` — either the
item's own action text verbatim, or an operator-supplied --summary. Multi-item
semantic merging (move.md's "Merge example") stays a manual, human-only step;
this only gives a hook-restricted caller a sanctioned way to get one finished
item out of an active section, even if the resulting summary is just the
original text carried over as-is.

Exit codes: 0 = ok, 1 = validation/match failure, 2 = usage error.
"""

from __future__ import annotations

import argparse
import datetime
try:
    import fcntl
except ImportError:
    fcntl = None
import hashlib
import io
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add_item import validate_marker, atomic_write, MAX_BODY_LINES, insert_item  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ITEM_RE = re.compile(r"^([ \t]*)-[ \t]+(\[[^\]]*\])[ \t]+(.*)$")

# A short one-line reference to a research/plan artefact -- the escape hatch the
# budget error message itself recommends -- is exempt from MAX_BODY_LINES. Without
# this, an item already at the cap has no sanctioned way to follow that advice:
# the reference note is itself one more line, so appending it would also be
# rejected, leaving no path back into budget (see add_item.py's fix_plan.md
# entry "update_item.py 10줄 예산 초과 항목의 append 막다른 길 해소"). The exemption is
# capped at REF_NOTE_MAX_LEN so it cannot be used to smuggle an arbitrarily long
# note in under the guise of a short reference.
REF_NOTE_MAX_LEN = 100


# ---------------------------------------------------------------- attribute slot
#
# A tracker line has two bracket slots.  The LEADING one is the checkbox marker
# (`[ ]` / `[x]` / `[-]` / `[BLOCKED:P#:owner]`), owned by validate_marker.  The
# TRAILING one carries per-item attributes, written as `[KEY:VALUE]` at the end of
# the action text.  Only the trailing slot is handled here, and only for keys this
# table registers -- an unregistered key is rejected rather than written, so the
# tracker cannot accumulate private vocabularies that no reader parses.
#
# `BLOCKED` is deliberately absent: it is a checkbox-marker value, not an
# attribute, so keeping it out of this table prevents a trailing `[BLOCKED:...]`
# from ever being emitted next to a real one.
ATTR_VOCAB: dict[str, re.Pattern[str]] = {
    # Impact / Confidence / Ease, each a number: [ICE:I2,C0.8,E4]
    "ICE": re.compile(r"^I\d+(?:\.\d+)?,C\d+(?:\.\d+)?,E\d+(?:\.\d+)?$"),
    # Execution channel, one of the five the operating model defines: [ch:orca]
    "ch": re.compile(r"^(?:orca|clawo|deep-tasks|in-session|user-decision)$"),
    # Which RAID axes are registered for this item: [RAID:R,D]
    "RAID": re.compile(r"^[RAID](?:,[RAID])*$"),
}


def validate_attr(key: str, value: str) -> None:
    """Reject an unregistered attribute key, or a value its grammar disallows."""
    if key not in ATTR_VOCAB:
        raise ValueError(
            f"unregistered attribute key {key!r}. Registered: "
            f"{', '.join(sorted(ATTR_VOCAB))}. Add the key to ATTR_VOCAB (and its "
            "grammar) before writing it, so every reader can parse it."
        )
    if not ATTR_VOCAB[key].match(value):
        raise ValueError(
            f"value {value!r} does not match the grammar registered for {key!r} "
            f"({ATTR_VOCAB[key].pattern})"
        )


def parse_attr_arg(arg: str) -> tuple[str, str]:
    """Split a `KEY=VALUE` argument, validating the pair."""
    if "=" not in arg:
        raise ValueError(f"--set-attr expects KEY=VALUE, got {arg!r}")
    key, _, value = arg.partition("=")
    key, value = key.strip(), value.strip()
    if not key or not value:
        raise ValueError(f"--set-attr expects a non-empty KEY and VALUE, got {arg!r}")
    validate_attr(key, value)
    return key, value


def attr_arg_type(arg: str) -> tuple[str, str]:
    """argparse `type=` adapter that preserves the rejection message.

    argparse swallows a ValueError from a type callable and prints its own generic
    "invalid <callable> value" line, which drops the registered keys and the value
    grammar -- the only parts of the message a caller can act on. ArgumentTypeError
    is printed verbatim, so the boundary re-raises as that instead.
    """
    try:
        return parse_attr_arg(arg)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def write_attr(action: str, key: str, value: str) -> str:
    """Set `[KEY:VALUE]` on the action text, replacing that key in place if present.

    Replacing in place rather than appending is what makes repeated writes
    idempotent and keeps a re-scored item from growing a second marker for the
    same key -- the failure mode hand-editing produces.
    """
    validate_attr(key, value)
    token = f"[{key}:{value}]"
    existing = re.compile(r"[ \t]*\[" + re.escape(key) + r":[^\]]*\]")
    if existing.search(action):
        return existing.sub(" " + token, action, count=1).rstrip()
    return f"{action.rstrip()} {token}"


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


def apply_update(
    block: list[str],
    set_marker: str | None,
    append_note: str | None,
    set_attr: tuple[str, str] | None = None,
) -> list[str]:
    block = list(block)

    if set_marker:
        m = ITEM_RE.match(block[0])
        assert m is not None
        block[0] = f"{m.group(1)}- {set_marker} {m.group(3)}"

    if set_attr:
        m = ITEM_RE.match(block[0])
        assert m is not None
        block[0] = f"{m.group(1)}- {m.group(2)} {write_attr(m.group(3), *set_attr)}"

    if append_note:
        m = ITEM_RE.match(block[0])
        assert m is not None
        indent = len(m.group(1))
        # Reuse the indent characters an existing sub-bullet already uses
        # (tabs vs spaces) instead of always emitting spaces -- a hardcoded
        # space indent mismatches tab-indented siblings and mixes styles
        # within one item.
        note_indent = None
        for existing in block[1:]:
            stripped = existing.lstrip(" \t")
            if stripped.startswith("-"):
                note_indent = existing[: len(existing) - len(stripped)]
                break
        if note_indent is None:
            note_indent = " " * (indent + 2)
        stripped_note = append_note.strip()
        note_line = f"{note_indent}- {stripped_note}"
        prospective_len = len(block) + 1
        if prospective_len > MAX_BODY_LINES and len(stripped_note) > REF_NOTE_MAX_LEN:
            raise ValueError(
                f"item body would grow to {prospective_len} lines, over the "
                f"{MAX_BODY_LINES}-line budget, and the note is {len(stripped_note)} "
                f"chars (over the {REF_NOTE_MAX_LEN}-char one-line-reference "
                "exemption). Move the note into a research-<slug>.md / "
                "plan-<slug>.md artefact and reference it with a short one-line "
                "sub-bullet instead (add.md 'Deliverable separation matrix')."
            )
        block.append(note_line)

    return block


def backup_file(path: str) -> str:
    """Copy `path` to a timestamped `.bak` sibling and return the backup path.

    Naming mirrors cleanup.py's convention. atomic_write() only guarantees
    crash safety (temp file + rename); it does not preserve the prior content.
    Only --delete needs preservation here: --move keeps the item's text alive
    in '## Completed', and --set-marker / --append-note edit in place, so
    --delete is the one mutation with nothing to recover from. The trackers
    this targets are commonly gitignored, so there is no VCS fallback either.

    The name is claimed with O_CREAT|O_EXCL rather than written straight
    through, because the timestamp only has 1-second resolution: two deletes
    landing in the same second would otherwise resolve to the same filename
    and the second copy would silently overwrite -- and destroy -- the first
    item's only backup. On a collision the seconds-suffix is disambiguated
    ('-1', '-2', ...) instead of overwriting.
    """
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    attempt = 0
    while True:
        suffix = "" if attempt == 0 else f"-{attempt}"
        backup_path = f"{path}.{stamp}{suffix}.bak"
        try:
            fd = os.open(backup_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            attempt += 1
            continue
        break
    try:
        with open(path, "rb") as src, os.fdopen(fd, "wb") as dst:
            shutil.copyfileobj(src, dst)
        shutil.copystat(path, backup_path)
    except BaseException:
        # never leave a half-written backup that a later recovery might trust
        try:
            os.unlink(backup_path)
        except OSError:
            pass
        raise
    return backup_path


def remove_block(lines: list[str], start: int, end: int) -> list[str]:
    """Delete lines[start:end] and collapse a resulting doubled blank line.

    find_item_block's `end` stops at the first blank line (or EOF/heading), so
    that trailing blank is NOT part of [start:end) -- it's the separator before
    whatever follows. Deleting only [start:end) would leave that separator
    immediately after the separator that preceded the removed item, i.e. two
    blank lines in a row. Collapse that one case; anything else (item removed
    from the very top/bottom of a section) is left as-is since there's nothing
    to double up.
    """
    new_lines = lines[:start] + lines[end:]
    if (
        0 < start < len(new_lines)
        and not new_lines[start - 1].strip()
        and not new_lines[start].strip()
    ):
        del new_lines[start]
    return new_lines


def perform_move(lines: list[str], start: int, end: int, summary: str | None) -> tuple[list[str], str]:
    """Extract the matched block, delete it, and return (new_lines, completed_line).

    completed_line is the marker-free '- <text>' entry the caller inserts into
    '## Completed' -- kept separate from the insert step so --dry-run can show
    it without writing, and so the caller decides where in Completed it lands.
    """
    m = ITEM_RE.match(lines[start])
    assert m is not None
    action_text = m.group(3)

    # `is not None`, not truthiness: `--summary ""` is an explicit (if useless)
    # operator choice and must reach the empty check below, not silently fall
    # back to the verbatim action text. Truthiness also made `--summary ""`
    # and `--summary " "` behave differently -- the latter already raised.
    text = summary.strip() if summary is not None else action_text
    if "\n" in text or "\r" in text:
        raise ValueError("--summary must be a single line (no newlines)")
    if not text:
        raise ValueError("--summary must not be empty")

    completed_line = f"- {text}"
    new_lines = remove_block(lines, start, end)
    return new_lines, completed_line


SECTION_RE = re.compile(r"^##[ \t]+(.*\S)[ \t]*$")

# format.md "Marker syntax" lists `- [x]` under `## Progress`, but real trackers
# also drive active work from project-specific sections (`## TODO`,
# `## Priority Tasks`, ...) and legitimately mark those `[x]` -- `sync.md` does
# exactly that before handing off to `move`. So this guard refuses only the two
# states format.md positively forbids, rather than allow-listing one section:
#   - any checkbox marker inside `## Completed` (summarised history, no checkboxes)
#   - `[x]` inside `## Hold`, which exists to park un-actionable BLOCKED items
COMPLETED_SECTION = "## Completed"
HOLD_SECTION = "## Hold"


def enclosing_section(lines: list[str], index: int) -> str | None:
    """Nearest `## ` heading at or above `index` (None when the item precedes any)."""
    for i in range(index, -1, -1):
        m = SECTION_RE.match(lines[i])
        if m:
            return f"## {m.group(1)}"
    return None


def validate_section_marker(section: str | None, marker: str) -> None:
    """Refuse a marker the item's own section does not permit.

    `add_item.py` already guards this on the insert path (it rejects active
    markers aimed at `## Completed`); without the same guard here the sanctioned
    *update* path can write a state the schema forbids -- which is exactly the
    corruption `block-direct-checklist-edit.js` blocks raw edits to prevent.
    """
    if section is None:
        return
    normalised = marker.strip()
    if section == COMPLETED_SECTION:
        raise ValueError(
            f"cannot set marker {normalised} on an item in {COMPLETED_SECTION!r} -- that "
            "section holds summarised historical lines without checkboxes (format.md "
            "'Marker syntax')"
        )
    if normalised == "[x]" and section == HOLD_SECTION:
        raise ValueError(
            f"cannot set {normalised} on an item in {HOLD_SECTION!r} -- that section "
            "parks un-actionable BLOCKED items, and format.md's marker table allows "
            "only '[ ]' / '[BLOCKED...]' there. Move the item back to an active "
            "section first, or use cleanup.py to migrate it into '## Completed'."
        )


def run_update(args: argparse.Namespace) -> int:
    has_delete = args.delete
    # Read defensively: namespaces predating --set-attr (including every
    # pre-existing caller and self-test namespace here) do not define it.
    set_attr = getattr(args, "set_attr", None)
    if not args.set_marker and not args.append_note and not args.move and not has_delete and not set_attr:
        raise ValueError(
            "at least one of --set-marker / --append-note / --set-attr / --move / --delete is required"
        )
    if args.move and (args.set_marker or args.append_note or has_delete or set_attr):
        raise ValueError("--move cannot be combined with other mutations (--set-marker / --append-note / --set-attr)")
    if has_delete and (args.set_marker or args.append_note or args.move or set_attr):
        raise ValueError("--delete cannot be combined with other mutations (--set-marker / --append-note / --set-attr)")
    if args.summary is not None and not args.move:
        raise ValueError("--summary only applies together with --move")
    if args.set_marker:
        validate_marker(args.set_marker)
    if args.append_note and ("\n" in args.append_note or "\r" in args.append_note):
        raise ValueError("--append-note must be a single line (no newlines)")
    if set_attr:
        # Validate up front so an unregistered key fails before the lock is taken
        # and before any write path is entered.
        validate_attr(*set_attr)

    if not os.path.exists(args.file):
        raise ValueError(f"tracker not found: {args.file}")

    # Hold an exclusive lock across the WHOLE read-modify-write, not just the read.
    # The lock needs its own file because atomic_write() replaces the tracker via
    # os.replace(): that swaps the inode, so a lock held on the tracker's own fd would
    # protect a file the writer no longer points at. Two concurrent updates could
    # otherwise both read the same state and have the later write silently drop the
    # earlier one's marker or progress note.
    #
    # It lives in the temp dir, keyed by a hash of the tracker's absolute path, rather
    # than beside the tracker: a `<tracker>.lock` sibling shows up as an untracked file
    # in the repo holding the tracker (`fix_plan.md` is typically gitignored, but a
    # `.lock` suffix is not), so it would leave visible debris on every update. Deriving
    # the name from the absolute path keeps every process addressing one tracker on the
    # same lock; losing the temp dir is harmless since the file is recreated on demand.
    lock_path = os.path.join(
        tempfile.gettempdir(),
        "fix-plan-" + hashlib.sha1(os.path.abspath(args.file).encode("utf-8")).hexdigest() + ".lock",
    )
    lock_fh = io.open(lock_path, "a+", encoding="utf-8")
    try:
        if fcntl:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)

        with io.open(args.file, "r", encoding="utf-8") as fh:
            src = fh.read()

        lines = src.split("\n")
        start, end, _indent = find_item_block(lines, args.match)

        if args.move:
            section = enclosing_section(lines, start)
            if section == COMPLETED_SECTION:
                raise ValueError(
                    f"item is already inside {COMPLETED_SECTION!r} -- nothing to move"
                )
            removed_block = lines[start:end]
            new_lines, completed_line = perform_move(lines, start, end, args.summary)
            out = insert_item("\n".join(new_lines), COMPLETED_SECTION, completed_line, "top")

            if args.dry_run:
                print("--- dry-run: removed from its active section ---")
                print("\n".join(removed_block))
                print(f"--- dry-run: inserted into {COMPLETED_SECTION!r} ---")
                print(completed_line)
                return 0

            atomic_write(args.file, out, prefix=".update_item.")
            print(f"OK: moved item matching --match {args.match!r} into {COMPLETED_SECTION!r} in {args.file}")
            print(completed_line)
            return 0

        if has_delete:
            removed_block = lines[start:end]
            new_lines = remove_block(lines, start, end)
            out = "\n".join(new_lines)
            if args.dry_run:
                print("--- dry-run: deleted block ---")
                print("\n".join(removed_block))
                return 0
            backup_path = backup_file(args.file)
            atomic_write(args.file, out, prefix=".update_item.")
            print(f"OK: deleted item matching --match {args.match!r} from {args.file}")
            print(f"Backup created at {backup_path}")
            return 0

        if args.set_marker:
            validate_section_marker(enclosing_section(lines, start), args.set_marker)
        block = apply_update(lines[start:end], args.set_marker, args.append_note, set_attr)

        out = "\n".join(lines[:start] + block + lines[end:])

        if args.dry_run:
            print("--- dry-run: item after update ---")
            print("\n".join(block))
            return 0

        atomic_write(args.file, out, prefix=".update_item.")
    finally:
        if fcntl:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
        lock_fh.close()

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

    # apply_update: append-note reuses tab indentation from an existing sibling
    tab_block = ["- [ ] tab-item", "\t- **Why**: r"]
    tab_updated = apply_update(tab_block, None, "tabnote")
    check("append-note matches an existing tab-indented sibling", tab_updated[-1] == "\t- tabnote")

    # apply_update: append-note falls back to spaces with no existing sub-bullet
    bare_block = ["- [ ] bare-item"]
    bare_updated = apply_update(bare_block, None, "first note")
    check("append-note falls back to 2-space indent with no siblings", bare_updated[-1] == "  - first note")

    # apply_update: budget enforcement
    padded_block = block + [f"  - pad {i}" for i in range(7)]  # 3 + 7 = 10 lines, +1 note = 11 > 10
    try:
        apply_update(padded_block, None, "one more line pushes it over budget, and this note is also long enough to fail the reference exemption")
        check("length budget enforced for a long note", False)
    except ValueError:
        check("length budget enforced for a long note", True)

    # apply_update: a short one-line artefact reference is exempt from the
    # budget even when the item is already over it (the escape hatch the
    # error message itself recommends must actually be reachable)
    ref_updated = apply_update(padded_block, None, "see plan-xyz.md")
    check(
        "short reference note is exempt from the length budget",
        ref_updated[-1] == "  - see plan-xyz.md",
    )
    check("reference-note exemption still grows the block by one line", len(ref_updated) == len(padded_block) + 1)

    # apply_update: a note right at REF_NOTE_MAX_LEN is exempt, one char over is not
    at_cap_note = "x" * REF_NOTE_MAX_LEN
    apply_update(padded_block, None, at_cap_note)  # must not raise
    check("note exactly at REF_NOTE_MAX_LEN is exempt", True)
    try:
        apply_update(padded_block, None, "x" * (REF_NOTE_MAX_LEN + 1))
        check("note one char over REF_NOTE_MAX_LEN is still rejected when over budget", False)
    except ValueError:
        check("note one char over REF_NOTE_MAX_LEN is still rejected when over budget", True)

    # run_update end-to-end via a temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("\n".join(doc_lines))
        tmp_path = tf.name
    try:
        class NS:
            # mirrors the argparse default so run_update can read args.delete
            # directly, exactly as it does for the sibling mutation flags
            delete = False
        ns = NS()
        ns.file = tmp_path
        ns.match = "unique-marker-beta"
        ns.set_marker = "[x]"
        ns.append_note = "done via update_item"
        ns.dry_run = False
        ns.move = False
        ns.summary = None
        rc = run_update(ns)
        check("run_update returns 0", rc == 0)
        with open(tmp_path, encoding="utf-8") as fh:
            result = fh.read()
        check("run_update wrote the new marker", "- [x] second item unique-marker-beta" in result)
        check("run_update wrote the note", "- done via update_item" in result)
        check("run_update left the other item untouched", "- [ ] first item unique-marker-alpha" in result)
    finally:
        os.unlink(tmp_path)

    # enclosing_section: nearest heading above the item
    check("enclosing_section finds the heading", enclosing_section(doc_lines, 4) == "## Priority Tasks")
    check("enclosing_section returns None above any heading", enclosing_section(doc_lines, 0) is None)

    # validate_section_marker: the two states format.md forbids
    for section, marker, should_raise, name in (
        ("## Hold", "[x]", True, "[x] rejected in ## Hold"),
        ("## Hold", "[ ]", False, "[ ] allowed in ## Hold"),
        ("## Hold", "[BLOCKED:P1:external]", False, "[BLOCKED] allowed in ## Hold"),
        ("## Completed", "[ ]", True, "any checkbox rejected in ## Completed"),
        ("## Progress", "[x]", False, "[x] allowed in ## Progress"),
        ("## TODO", "[x]", False, "[x] allowed in a project-specific active section"),
        (None, "[x]", False, "no enclosing heading is permissive"),
    ):
        try:
            validate_section_marker(section, marker)
            check(name, not should_raise)
        except ValueError:
            check(name, should_raise)

    # end-to-end: the Hold case row 10 actually reproduced
    import tempfile as _tf
    hold_doc = [
        "# T", "", "## Hold", "",
        "- [BLOCKED:P1:external] parked item unique-marker-hold",
        "  - **Why**: waiting", "",
    ]
    with _tf.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("\n".join(hold_doc))
        hold_path = tf.name
    try:
        class NS3:
            # mirrors the argparse default so run_update can read args.delete
            # directly, exactly as it does for the sibling mutation flags
            delete = False
        ns3 = NS3()
        ns3.file = hold_path
        ns3.match = "unique-marker-hold"
        ns3.set_marker = "[x]"
        ns3.append_note = None
        ns3.dry_run = False
        ns3.move = False
        ns3.summary = None
        try:
            run_update(ns3)
            check("run_update refuses [x] in ## Hold", False)
        except ValueError:
            check("run_update refuses [x] in ## Hold", True)
        with open(hold_path, encoding="utf-8") as fh:
            check("rejected update left the file untouched", "[BLOCKED:P1:external]" in fh.read())
        # a note (no marker change) is still allowed in ## Hold
        ns3.set_marker = None
        ns3.append_note = "still waiting on upstream"
        check("append-note still works in ## Hold", run_update(ns3) == 0)
    finally:
        os.unlink(hold_path)

    # sidecar lock: created next to the tracker, and the tracker itself is replaced
    with _tf.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("\n".join(doc_lines))
        lock_doc = tf.name
    try:
        class NS4:
            # mirrors the argparse default so run_update can read args.delete
            # directly, exactly as it does for the sibling mutation flags
            delete = False
        ns4 = NS4()
        ns4.file = lock_doc
        ns4.match = "unique-marker-alpha"
        ns4.set_marker = None
        ns4.append_note = "locked write"
        ns4.dry_run = False
        ns4.move = False
        ns4.summary = None
        check("run_update with sidecar lock returns 0", run_update(ns4) == 0)
        check("lock file is NOT left beside the tracker", not os.path.exists(lock_doc + ".lock"))
        _lock = os.path.join(
            tempfile.gettempdir(),
            "fix-plan-" + hashlib.sha1(os.path.abspath(lock_doc).encode("utf-8")).hexdigest() + ".lock",
        )
        check("lock file lives in the temp dir", os.path.exists(_lock))
        with open(lock_doc, encoding="utf-8") as fh:
            check("locked write landed", "- locked write" in fh.read())
        # dry-run must not mutate, even holding the lock
        before = open(lock_doc, encoding="utf-8").read()
        ns4.append_note = "should not persist"
        ns4.dry_run = True
        run_update(ns4)
        check("dry-run leaves the tracker byte-identical", open(lock_doc, encoding="utf-8").read() == before)
    finally:
        os.unlink(lock_doc)

    # missing tracker file
    try:
        class NS2:
            # mirrors the argparse default so run_update can read args.delete
            # directly, exactly as it does for the sibling mutation flags
            delete = False
        ns2 = NS2()
        ns2.file = "/nonexistent/path/fix_plan.md"
        ns2.match = "x"
        ns2.set_marker = "[x]"
        ns2.append_note = None
        ns2.dry_run = False
        ns2.move = False
        ns2.summary = None
        run_update(ns2)
        check("missing tracker raises", False)
    except ValueError:
        check("missing tracker raises", True)

    # --move: mechanical Move-step (Issue #436)

    # remove_block: deleting a middle item collapses the doubled blank line
    move_fixture = [
        "# T", "",
        "## Priority Tasks", "",
        "- [ ] item A", "  - **Why**: a", "",
        "- [x] item B unique-move-target", "  - **Why**: b", "  - **How to apply**: steps for b", "",
        "- [ ] item C", "  - **Why**: c", "",
        "## Completed", "",
        "- pre-existing completed line", "",
    ]
    b_start, b_end, _ = find_item_block(move_fixture, "unique-move-target")
    removed = remove_block(move_fixture, b_start, b_end)
    check("remove_block deletes the matched block", not any("unique-move-target" in ln for ln in removed))
    check("remove_block collapses the doubled blank line", "\n".join(removed).count("\n\n\n") == 0)
    check("remove_block leaves neighboring items intact", "item A" in "\n".join(removed) and "item C" in "\n".join(removed))

    # perform_move: verbatim vs --summary
    _, completed_line_verbatim = perform_move(move_fixture, b_start, b_end, None)
    check("perform_move verbatim uses the action text, marker-free", completed_line_verbatim == "- item B unique-move-target")
    _, completed_line_summary = perform_move(move_fixture, b_start, b_end, "condensed summary text")
    check("perform_move --summary overrides the verbatim text", completed_line_summary == "- condensed summary text")
    try:
        perform_move(move_fixture, b_start, b_end, "")
        check("perform_move rejects an explicitly empty --summary", False)
    except ValueError:
        check("perform_move rejects an explicitly empty --summary", True)
    try:
        perform_move(move_fixture, b_start, b_end, "   ")
        check("perform_move rejects a whitespace-only --summary", False)
    except ValueError:
        check("perform_move rejects a whitespace-only --summary", True)
    try:
        perform_move(move_fixture, b_start, b_end, "two\nlines")
        check("perform_move rejects a multi-line --summary", False)
    except ValueError:
        check("perform_move rejects a multi-line --summary", True)

    # run_update --move end-to-end: active-section [x] item (with sub-bullets) -> one-line Completed entry
    with _tf.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("\n".join(move_fixture))
        move_path = tf.name
    try:
        class NS5:
            # mirrors the argparse default so run_update can read args.delete
            # directly, exactly as it does for the sibling mutation flags
            delete = False
        ns5 = NS5()
        ns5.file = move_path
        ns5.match = "unique-move-target"
        ns5.set_marker = None
        ns5.append_note = None
        ns5.dry_run = False
        ns5.move = True
        ns5.summary = None

        # An explicitly empty --summary without --move must still trip the
        # "only applies together with --move" guard; truthiness let it pass.
        ns_empty = NS5()
        ns_empty.file = move_path
        ns_empty.match = "unique-move-target"
        ns_empty.set_marker = "[x]"
        ns_empty.append_note = None
        ns_empty.dry_run = True
        ns_empty.move = False
        ns_empty.summary = ""
        try:
            run_update(ns_empty)
            check("run_update rejects an explicitly empty --summary without --move", False)
        except ValueError:
            check("run_update rejects an explicitly empty --summary without --move", True)

        rc = run_update(ns5)
        check("run_update --move returns 0", rc == 0)
        with open(move_path, encoding="utf-8") as fh:
            after_move = fh.read()
        check(
            "run_update --move removed the block from Priority Tasks",
            "- [x] item B unique-move-target" not in after_move,
        )
        check(
            "run_update --move added a marker-free one-line entry to Completed",
            "- item B unique-move-target" in after_move
            and after_move.index("- item B unique-move-target") > after_move.index("## Completed"),
        )
        check("run_update --move preserved the pre-existing Completed entry", "pre-existing completed line" in after_move)
        check("run_update --move left sibling active items untouched", "item A" in after_move and "item C" in after_move)

        # run_update --delete dry-run: must print the block and write nothing
        ns_dry = NS5()
        ns_dry.file = move_path
        ns_dry.match = "item A"
        ns_dry.set_marker = None
        ns_dry.append_note = None
        ns_dry.dry_run = True
        ns_dry.move = False
        ns_dry.delete = True
        ns_dry.summary = None
        with open(move_path, encoding="utf-8") as fh:
            before_dry = fh.read()
        check("run_update --delete --dry-run returns 0", run_update(ns_dry) == 0)
        with open(move_path, encoding="utf-8") as fh:
            check("run_update --delete --dry-run left the file untouched", fh.read() == before_dry)

        # --delete rejects being combined with any other mutation
        for attr, value, label in (
            ("set_marker", "[x]", "--set-marker"),
            ("append_note", "note", "--append-note"),
            ("move", True, "--move"),
        ):
            ns_bad = NS5()
            ns_bad.file = move_path
            ns_bad.match = "item A"
            ns_bad.set_marker = None
            ns_bad.append_note = None
            ns_bad.dry_run = False
            ns_bad.move = False
            ns_bad.delete = True
            ns_bad.summary = None
            setattr(ns_bad, attr, value)
            try:
                run_update(ns_bad)
                rejected = False
            except ValueError:
                rejected = True
            check(f"run_update --delete rejects being combined with {label}", rejected)

        # run_update --delete test: remove an active item completely
        ns_del = NS5()
        ns_del.file = move_path
        ns_del.match = "item A"
        ns_del.set_marker = None
        ns_del.append_note = None
        ns_del.dry_run = False
        ns_del.move = False
        ns_del.delete = True
        ns_del.summary = None
        rc_del = run_update(ns_del)
        check("run_update --delete returns 0", rc_del == 0)
        with open(move_path, encoding="utf-8") as fh:
            after_del = fh.read()
        check("run_update --delete removed the target item", "item A" not in after_del)
        check("run_update --delete left neighboring item C intact", "item C" in after_del)
        def _backups_of(target: str) -> list[str]:
            d = os.path.dirname(target)
            base = os.path.basename(target) + "."
            return sorted(
                os.path.join(d, n) for n in os.listdir(d)
                if n.startswith(base) and n.endswith(".bak")
            )

        del_backups = _backups_of(move_path)
        check("run_update --delete wrote exactly one .bak backup", len(del_backups) == 1)
        if del_backups:
            with open(del_backups[0], encoding="utf-8") as fh:
                check("run_update --delete backup still contains the deleted item", "item A" in fh.read())

        # REGRESSION: two deletes inside the same second must not collide.
        # The backup name only has 1-second resolution, so an unguarded
        # implementation overwrites -- and destroys -- the first item's only
        # backup. Both deletes here run in-process, guaranteeing one second.
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
            tf.write(
                "# tracker\n\n## Progress\n\n"
                "- [ ] collide-one unique-collide\n  - **Why**: a\n  - **How to apply**: b\n\n"
                "- [ ] collide-two unique-collide\n  - **Why**: c\n  - **How to apply**: d\n"
            )
            collide_path = tf.name
        try:
            for target in ("collide-one", "collide-two"):
                ns_c = NS5()
                ns_c.file = collide_path
                ns_c.match = target
                ns_c.set_marker = None
                ns_c.append_note = None
                ns_c.dry_run = False
                ns_c.move = False
                ns_c.delete = True
                ns_c.summary = None
                run_update(ns_c)
            collide_backups = _backups_of(collide_path)
            check(
                "two same-second --delete runs produce two distinct backups",
                len(collide_backups) == 2,
            )
            preserved = set()
            for b in collide_backups:
                with open(b, encoding="utf-8") as fh:
                    body = fh.read()
                for target in ("collide-one", "collide-two"):
                    if target in body:
                        preserved.add(target)
            check(
                "neither same-second --delete lost its backed-up item",
                preserved == {"collide-one", "collide-two"},
            )
        finally:
            for leftover in _backups_of(collide_path) + [collide_path]:
                if os.path.exists(leftover):
                    os.unlink(leftover)

        # detect_bloated_tasks.py no longer flags the moved item's old '[x]' marker
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from detect_bloated_tasks import detect_bloated_tasks  # noqa: E402
        from pathlib import Path
        _ok, completed_in_active, _unmarked = detect_bloated_tasks(Path(move_path))
        check(
            "detect_bloated_tasks.py no longer flags the moved item",
            not any("unique-move-target" in ln for _lineno, ln in completed_in_active),
        )
    finally:
        os.unlink(move_path)

    # run_update --move --dry-run: preview only, tracker byte-identical afterward
    with _tf.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("\n".join(move_fixture))
        move_dry_path = tf.name
    try:
        before_dry = open(move_dry_path, encoding="utf-8").read()

        class NS6:
            # mirrors the argparse default so run_update can read args.delete
            # directly, exactly as it does for the sibling mutation flags
            delete = False
        ns6 = NS6()
        ns6.file = move_dry_path
        ns6.match = "unique-move-target"
        ns6.set_marker = None
        ns6.append_note = None
        ns6.dry_run = True
        ns6.move = True
        ns6.summary = "would-be summary"
        rc = run_update(ns6)
        check("run_update --move --dry-run returns 0", rc == 0)
        check(
            "run_update --move --dry-run leaves the tracker byte-identical",
            open(move_dry_path, encoding="utf-8").read() == before_dry,
        )
    finally:
        os.unlink(move_dry_path)

    # --move combined with --set-marker / --append-note is rejected
    try:
        class NS7:
            # mirrors the argparse default so run_update can read args.delete
            # directly, exactly as it does for the sibling mutation flags
            delete = False
        ns7 = NS7()
        ns7.file = "/nonexistent/irrelevant.md"
        ns7.match = "x"
        ns7.set_marker = "[x]"
        ns7.append_note = None
        ns7.dry_run = False
        ns7.move = True
        ns7.summary = None
        run_update(ns7)
        check("--move rejects being combined with --set-marker", False)
    except ValueError:
        check("--move rejects being combined with --set-marker", True)

    # --summary without --move is rejected
    try:
        class NS8:
            # mirrors the argparse default so run_update can read args.delete
            # directly, exactly as it does for the sibling mutation flags
            delete = False
        ns8 = NS8()
        ns8.file = "/nonexistent/irrelevant.md"
        ns8.match = "x"
        ns8.set_marker = None
        ns8.append_note = None
        ns8.dry_run = False
        ns8.move = False
        ns8.summary = "orphan summary"
        run_update(ns8)
        check("--summary without --move is rejected", False)
    except ValueError:
        check("--summary without --move is rejected", True)

    # --move on an item already inside '## Completed' is rejected. Ordinary Completed
    # entries are marker-free ('- text', per validate_section_marker's schema) so they
    # never match ITEM_RE in the first place -- this exercises the guard against the
    # data-integrity anomaly of a stray checkbox marker having ended up in Completed.
    already_completed_fixture = [
        "# T", "", "## Completed", "", "- [x] item D unique-already-completed", "",
    ]
    with _tf.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("\n".join(already_completed_fixture))
        already_path = tf.name
    try:
        class NS9:
            # mirrors the argparse default so run_update can read args.delete
            # directly, exactly as it does for the sibling mutation flags
            delete = False
        ns9 = NS9()
        ns9.file = already_path
        ns9.match = "unique-already-completed"
        ns9.set_marker = None
        ns9.append_note = None
        ns9.dry_run = False
        ns9.move = True
        ns9.summary = None
        run_update(ns9)
        check("--move on an already-Completed item is rejected", False)
    except ValueError:
        check("--move on an already-Completed item is rejected", True)
    finally:
        os.unlink(already_path)


    # ------------------------------------------------------------------
    # attribute slot (--set-attr KEY=VALUE)
    #
    # The tracker line has two marker slots: the leading checkbox marker, which
    # this script already writes and validates, and a trailing bracket slot that
    # it does not know about at all.  Measured consequence: the vocabularies the
    # tool writes reach 35.8% / 265 items, while every trailing-slot vocabulary
    # sits at 0-4.7% because each one is hand-typed.  These cases drive a general
    # trailing-slot writer with a registered vocabulary, so a new attribute is a
    # table entry rather than a new code path.
    #
    # Written before the implementation: each probe resolves the symbol through
    # globals() so a missing feature is reported as a FAIL, not raised as a
    # NameError that would abort the remaining cases.
    # ------------------------------------------------------------------
    _vocab = globals().get("ATTR_VOCAB")
    _validate_attr = globals().get("validate_attr")
    _parse_attr_arg = globals().get("parse_attr_arg")

    def attr_check(name: str, fn, want=None, raises=None) -> None:
        try:
            got = fn()
        except Exception as exc:  # noqa: BLE001 - absence must read as FAIL
            check(name, raises is not None and isinstance(exc, raises))
            return
        if raises is not None:
            check(name, False)
            return
        check(name, got == want if want is not None else bool(got))

    check("ATTR_VOCAB registry exists", isinstance(_vocab, dict))
    check("ATTR_VOCAB registers the ICE key", bool(_vocab) and "ICE" in _vocab)
    check("ATTR_VOCAB registers the channel key", bool(_vocab) and "ch" in _vocab)
    check("ATTR_VOCAB registers the RAID key", bool(_vocab) and "RAID" in _vocab)

    attr_check("validate_attr accepts a well-formed ICE value",
               lambda: _validate_attr("ICE", "I2,C0.8,E4") is None, want=True)
    attr_check("validate_attr rejects an unregistered key",
               lambda: _validate_attr("NOPE", "x"), raises=ValueError)
    attr_check("validate_attr rejects an ICE value missing a component",
               lambda: _validate_attr("ICE", "I2,C0.8"), raises=ValueError)
    attr_check("validate_attr rejects a non-numeric ICE component",
               lambda: _validate_attr("ICE", "I2,Chigh,E4"), raises=ValueError)
    attr_check("validate_attr accepts a registered channel value",
               lambda: _validate_attr("ch", "orca") is None, want=True)
    attr_check("validate_attr rejects an unregistered channel value",
               lambda: _validate_attr("ch", "telepathy"), raises=ValueError)

    attr_check("parse_attr_arg splits KEY=VALUE",
               lambda: _parse_attr_arg("ICE=I2,C0.8,E4"), want=("ICE", "I2,C0.8,E4"))
    attr_check("parse_attr_arg rejects a missing '='",
               lambda: _parse_attr_arg("ICE"), raises=ValueError)

    attr_block = [
        "- [ ] attr target item unique-marker-gamma",
        "  - **Why**: gamma reason",
        "  - **How to apply**: gamma steps",
    ]

    attr_check("apply_update writes the attribute at end of the item line",
               lambda: apply_update(attr_block, None, None, ("ICE", "I2,C0.8,E4"))[0],
               want="- [ ] attr target item unique-marker-gamma [ICE:I2,C0.8,E4]")
    attr_check("apply_update leaves sub-bullets untouched when writing an attribute",
               lambda: apply_update(attr_block, None, None, ("ICE", "I2,C0.8,E4"))[1:],
               want=attr_block[1:])
    attr_check("writing an attribute twice is idempotent",
               lambda: apply_update(
                   apply_update(attr_block, None, None, ("ICE", "I2,C0.8,E4")),
                   None, None, ("ICE", "I2,C0.8,E4"))[0],
               want="- [ ] attr target item unique-marker-gamma [ICE:I2,C0.8,E4]")
    attr_check("re-writing the same key replaces it in place rather than appending",
               lambda: apply_update(
                   apply_update(attr_block, None, None, ("ICE", "I2,C0.8,E4")),
                   None, None, ("ICE", "I5,C0.9,E1"))[0],
               want="- [ ] attr target item unique-marker-gamma [ICE:I5,C0.9,E1]")
    attr_check("writing a second key preserves the first",
               lambda: apply_update(
                   apply_update(attr_block, None, None, ("ICE", "I2,C0.8,E4")),
                   None, None, ("ch", "orca"))[0],
               want="- [ ] attr target item unique-marker-gamma [ICE:I2,C0.8,E4] [ch:orca]")
    attr_check("an attribute write preserves a BLOCKED checkbox marker",
               lambda: apply_update(
                   ["- [BLOCKED:P1:selfable] blocked attr target"], None, None, ("ch", "clawo"))[0],
               want="- [BLOCKED:P1:selfable] blocked attr target [ch:clawo]")
    attr_check("an attribute write combines with --set-marker in one call",
               lambda: apply_update(attr_block, "[x]", None, ("ICE", "I2,C0.8,E4"))[0],
               want="- [x] attr target item unique-marker-gamma [ICE:I2,C0.8,E4]")


    # ------------------------------------------------------------------
    # --set-attr CLI wiring
    #
    # apply_update already accepts an attribute, but nothing reaches it from the
    # command line, so the capability is unusable from a skill invocation. These
    # cases drive the wiring: the flag must satisfy the "at least one mutation"
    # requirement on its own, refuse to combine with the whole-item operations
    # (--move / --delete) exactly as --set-marker does, reject an unregistered key
    # before the tracker is touched, and honour --dry-run.
    #
    # The last case pins backward compatibility: a namespace built WITHOUT a
    # set_attr attribute must still run, because every pre-existing caller and
    # self-test namespace in this file is built that way.
    # ------------------------------------------------------------------
    import tempfile as _tf

    def _attr_tracker() -> str:
        with _tf.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write("\n".join([
                "# T", "", "## TODO", "",
                "- [ ] attr cli target unique-marker-delta",
                "  - **Why**: delta reason",
                "  - **How to apply**: delta steps",
                "",
            ]))
            return fh.name

    def _attr_ns(path: str, **over):
        class NS:
            delete = False
        ns = NS()
        ns.file = path
        ns.match = "unique-marker-delta"
        ns.set_marker = None
        ns.append_note = None
        ns.dry_run = False
        ns.move = False
        ns.summary = None
        ns.set_attr = None
        for k, v in over.items():
            setattr(ns, k, v)
        return ns

    _p = _attr_tracker()
    try:
        rc = run_update(_attr_ns(_p, set_attr=("ICE", "I2,C0.8,E4")))
        body = open(_p, encoding="utf-8").read()
        check("--set-attr alone satisfies the at-least-one-mutation check", rc == 0)
        check("--set-attr writes the marker into the tracker",
              "- [ ] attr cli target unique-marker-delta [ICE:I2,C0.8,E4]" in body)
    except Exception as exc:  # noqa: BLE001
        check("--set-attr alone satisfies the at-least-one-mutation check", False)
        check("--set-attr writes the marker into the tracker", False)
    finally:
        os.unlink(_p)

    _p = _attr_tracker()
    try:
        run_update(_attr_ns(_p, set_attr=("ICE", "I2,C0.8,E4"), move=True))
        check("--set-attr cannot be combined with --move", False)
    except ValueError as exc:
        check("--set-attr cannot be combined with --move", "set-attr" in str(exc))
    except Exception:  # noqa: BLE001
        check("--set-attr cannot be combined with --move", False)
    finally:
        os.unlink(_p)

    _p = _attr_tracker()
    try:
        run_update(_attr_ns(_p, set_attr=("ICE", "I2,C0.8,E4"), delete=True))
        check("--set-attr cannot be combined with --delete", False)
    except ValueError as exc:
        check("--set-attr cannot be combined with --delete", "set-attr" in str(exc))
    except Exception:  # noqa: BLE001
        check("--set-attr cannot be combined with --delete", False)
    finally:
        os.unlink(_p)

    _p = _attr_tracker()
    try:
        run_update(_attr_ns(_p, set_attr=("NOPE", "x")))
        check("--set-attr rejects an unregistered key", False)
    except ValueError as exc:
        check("--set-attr rejects an unregistered key", "unregistered attribute key" in str(exc))
    except Exception:  # noqa: BLE001
        check("--set-attr rejects an unregistered key", False)
    else:
        pass
    finally:
        unchanged = open(_p, encoding="utf-8").read()
        check("a rejected key leaves the tracker untouched", "[NOPE:" not in unchanged)
        os.unlink(_p)

    _p = _attr_tracker()
    try:
        run_update(_attr_ns(_p, set_marker="[x]", set_attr=("ch", "orca")))
        body = open(_p, encoding="utf-8").read()
        check("--set-attr combines with --set-marker in one invocation",
              "- [x] attr cli target unique-marker-delta [ch:orca]" in body)
    except Exception:  # noqa: BLE001
        check("--set-attr combines with --set-marker in one invocation", False)
    finally:
        os.unlink(_p)

    _p = _attr_tracker()
    try:
        before = open(_p, encoding="utf-8").read()
        run_update(_attr_ns(_p, set_attr=("RAID", "R,D"), dry_run=True))
        check("--dry-run with --set-attr leaves the tracker unwritten",
              open(_p, encoding="utf-8").read() == before)
    except Exception:  # noqa: BLE001
        check("--dry-run with --set-attr leaves the tracker unwritten", False)
    finally:
        os.unlink(_p)

    _p = _attr_tracker()
    try:
        legacy = _attr_ns(_p, set_marker="[x]")
        del legacy.set_attr  # a namespace predating the flag
        check("a namespace without set_attr still runs", run_update(legacy) == 0)
    except Exception:  # noqa: BLE001
        check("a namespace without set_attr still runs", False)
    finally:
        os.unlink(_p)


    def _run_capture(fn, arg: str, needle: str) -> bool:
        """True when calling fn(arg) raises an error whose message contains needle."""
        if not callable(fn):
            return False
        try:
            fn(arg)
        except Exception as exc:  # noqa: BLE001
            return needle in str(exc)
        return False


    # ------------------------------------------------------------------
    # argparse error surfacing
    #
    # argparse replaces a ValueError raised by a `type=` callable with its own
    # generic "invalid <callable> value" line, which discards the part of the
    # message that carries the registered keys and the value grammar. That message
    # is the whole value of the vocabulary guard -- a rejection that does not say
    # what IS allowed sends the caller to the source. Observed on the real CLI:
    #   update_item.py: error: argument --set-attr: invalid parse_attr_arg value: 'NOPE=x'
    #
    # So the argparse boundary needs its own adapter. parse_attr_arg keeps raising
    # ValueError (its own tests pin that); the adapter re-raises as
    # ArgumentTypeError, which argparse prints verbatim.
    # ------------------------------------------------------------------
    _attr_arg_type = globals().get("attr_arg_type")
    check("attr_arg_type adapter exists", callable(_attr_arg_type))

    attr_check("attr_arg_type returns the parsed pair for valid input",
               lambda: _attr_arg_type("ICE=I2,C0.8,E4"), want=("ICE", "I2,C0.8,E4"))
    attr_check("attr_arg_type raises ArgumentTypeError for an unregistered key",
               lambda: _attr_arg_type("NOPE=x"), raises=argparse.ArgumentTypeError)
    attr_check("the unregistered-key message still names the registered keys",
               lambda: _run_capture(_attr_arg_type, "NOPE=x", "Registered:"), want=True)
    attr_check("the bad-value message still names the grammar",
               lambda: _run_capture(_attr_arg_type, "ICE=I2,C0.8", "does not match the grammar"),
               want=True)

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> int:
    p = argparse.ArgumentParser(
        description="Flip the marker on, or append a progress note to, an EXISTING fix_plan/checklist item"
    )
    p.add_argument("--test", action="store_true", help="run the self-test and exit")
    p.add_argument("--file", help="tracker path (fix_plan.md or checklist.md)")
    p.add_argument(
        "--set-attr",
        type=attr_arg_type,
        metavar="KEY=VALUE",
        help="set a trailing [KEY:VALUE] attribute on the item "
             "(registered keys: " + ", ".join(sorted(ATTR_VOCAB)) + ")",
    )
    p.add_argument("--match", help="substring of the target item's action text (must match exactly one item)")
    p.add_argument("--set-marker", help="'[ ]', '[x]', '[-]', or '[BLOCKED:P<0-3>:external|selfable]'")
    p.add_argument("--append-note", help="one-line progress note appended as a new sub-bullet")
    p.add_argument(
        "--move",
        action="store_true",
        help="move the matched item into '## Completed' as a marker-free one-line entry "
        "(mechanical Move step -- see module docstring)",
    )
    p.add_argument(
        "--summary",
        help="operator-supplied one-line text to use in '## Completed' instead of the "
        "item's own action text verbatim (only valid together with --move)",
    )
    p.add_argument(
        "--delete",
        action="store_true",
        help="delete the matched item and its sub-bullets completely (e.g. for promoted drafts or superseded stubs)",
    )
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
