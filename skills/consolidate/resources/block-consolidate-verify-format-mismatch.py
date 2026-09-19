#!/usr/bin/env python3
r"""PreToolUse hook: block Internal Code Review / AI Review Summary POSTs whose
body shape would fail `verify_consolidate.py`'s finding-count reconciliation
(checks "Table row completeness" and "Superpowers inclusion").

Why this exists
----------------
`verify_consolidate.py` counts internal-review findings by regex against the
posted Internal Code Review body: `^####\\s+\\d+\\.` (falling back to
`^####\\s+\`` then `^####\\s+\\S`). A body that lists findings as a bolded
subheading + plain numbered list (`**🟠 Important**\n\n1. ...`) instead of a
level-4 heading per finding (`#### 1. <title> (🟠 Important)`) counts as ZERO
internal findings, so the row-count check ("table has 7 rows" vs "expected 0")
fails — and even once headings are fixed, the Summary's findings-table `Source`
column must additionally carry the literal substring `superpowers` for
internal-origin rows (`internal_findings > 0` and `len(superpowers_in_table) == 0`
is the second, independent failure mode of the same script). Both surfaced in
the same PR review session (2026-09-18, `daegunsoftDev/gitops` PR #45) as two
separate PATCH cycles that could have been caught before the first POST.

I/O contract (cross-platform, mirrors block-summary-status-vocab.py)
----------------------------------------------------------------------
  - Claude Code: stdin {tool_name, tool_input.command}; block = exit 2 + stderr
  - Antigravity: stdin {toolCall.name, toolCall.args.*}; block = stdout
                 {"decision":"deny","reason":...} + exit 0

Bypass (per-command only, never session-wide):
    ALLOW_CONSOLIDATE_VERIFY_FORMAT=1 <command>
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

INTERNAL_MARKER = "Internal Code Review"
SUMMARY_MARKER = "AI Review Summary"

HEADING_RE = re.compile(r"^####\s+\S", re.MULTILINE)
NUMBERED_HEADING_RE = re.compile(r"^####\s+\d+\.", re.MULTILINE)
# A finding-shaped numbered list item at the top level of the body, e.g.
# "1. **[...]** ..." or "1. `/god-mode/` ...". Used only to detect the case
# where findings exist but are NOT expressed as `####` headings.
TOPLEVEL_NUMBERED_ITEM_RE = re.compile(r"^\d+\.\s+\S", re.MULTILINE)


def emit_block(runtime: str, reason: str) -> None:
    if runtime == "antigravity":
        print(json.dumps({"decision": "deny", "reason": reason}, ensure_ascii=False))
        sys.exit(0)
    sys.stderr.write(reason + "\n")
    sys.exit(2)


def read_input() -> tuple[str, str]:
    """Return (runtime, command). ('', '') means "not our business"."""
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return "", ""
    if data.get("tool_name"):
        if data["tool_name"] != "Bash":
            return "", ""
        return "claude", (data.get("tool_input") or {}).get("command", "") or ""
    call = data.get("toolCall") or {}
    if call.get("name"):
        if call["name"] != "run_command":
            return "", ""
        args = call.get("args") or {}
        cmd = args.get("command") or args.get("CommandLine") or ""
        return "antigravity", cmd if isinstance(cmd, str) else json.dumps(args)
    return "", ""


def is_comment_or_review_post(command: str) -> bool:
    """Does this command publish/patch a PR review or a PR/issue comment?"""
    if re.search(r"\bgh\s+(pr|issue)\s+comment\b", command):
        return True
    if re.search(r"\bgh\s+pr\s+review\b", command):
        return True
    # gh api POST/PATCH/PUT .../reviews or .../comments/<id>
    if re.search(r"\bgh\s+api\b", command) and re.search(
        r"pulls/\d*/?reviews\b|issues/comments/\d+|issues/\d*/?comments\b", command
    ):
        return True
    return False


def extract_bodies(command: str) -> list[str]:
    """Collect every candidate body reachable from the command line."""
    bodies: list[str] = []
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    def read_file(path: str) -> None:
        try:
            with open(path, encoding="utf-8") as fh:
                bodies.append(fh.read())
        except OSError:
            pass

    for i, tok in enumerate(tokens):
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if tok in ("--body-file", "-F") and nxt:
            read_file(nxt)
        elif tok == "--input" and nxt:
            try:
                with open(nxt, encoding="utf-8") as fh:
                    payload = json.load(fh)
                if isinstance(payload, dict) and isinstance(payload.get("body"), str):
                    bodies.append(payload["body"])
                if isinstance(payload, dict) and isinstance(payload.get("comments"), list):
                    pass  # inline comments are not the findings body; ignored here
            except (OSError, ValueError):
                pass
        elif tok in ("--body", "-b") and nxt:
            bodies.append(nxt)
        elif tok == "-f" and nxt.startswith("body="):
            bodies.append(nxt[len("body="):])
        elif tok.startswith("--body="):
            bodies.append(tok[len("--body="):])
    return bodies


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def find_findings_tables(body: str) -> list[tuple[list[str], list[list[str]]]]:
    """Return [(header_cells, data_rows)] for tables that look like findings
    tables (at least one row whose first cell is a bare number)."""
    tables = []
    block: list[str] = []
    for line in body.splitlines() + [""]:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            block.append(stripped)
            continue
        if len(block) >= 3:
            header = split_row(block[0])
            rows = [split_row(r) for r in block[2:]]
            if any(r and r[0].isdigit() for r in rows):
                tables.append((header, [r for r in rows if r and r[0].isdigit()]))
        block = []
    return tables


def check_internal_review_headings(body: str) -> str | None:
    """Internal Code Review body: findings must be `#### N.` headings, not a
    plain numbered list under a bold subheading. Returns a block reason or
    None."""
    if INTERNAL_MARKER not in body:
        return None
    if HEADING_RE.search(body):
        return None  # at least one heading-shaped finding exists — OK
    if not TOPLEVEL_NUMBERED_ITEM_RE.search(body):
        return None  # no findings at all (e.g. "no actionable findings") — OK
    sample = TOPLEVEL_NUMBERED_ITEM_RE.search(body)
    sample_line = sample.group(0)[:80] if sample else ""
    return (
        "[hook:block-consolidate-verify-format-mismatch] BLOCKED — Internal Code "
        "Review body lists findings as a plain numbered list, not `#### N.` "
        "headings.\n"
        f"  first offending line: {sample_line!r}\n\n"
        "verify_consolidate.py counts internal findings via `^####\\s+\\d+\\.` "
        "(falling back to `^####\\s+\\``, `^####\\s+\\S`). A numbered list under a "
        "bold subheading (`**🟠 Important**\\n\\n1. ...`) matches none of these — "
        "the finding count reads 0 and the table-row-count check fails.\n\n"
        "Use one `#### N. <title> (<severity>)` heading per finding, e.g.:\n"
        "  #### 1. `/god-mode/` exclusion safety unverified (🟠 Important)\n\n"
        "Bypass (only if you are certain): ALLOW_CONSOLIDATE_VERIFY_FORMAT=1 <command>"
    )


def check_summary_superpowers_source(body: str) -> str | None:
    """AI Review Summary body: any findings-table row sourced from the internal
    review must have 'superpowers' in its Source cell. Returns a block reason
    or None."""
    if SUMMARY_MARKER not in body:
        return None
    for header, rows in find_findings_tables(body):
        lowered = [h.lower() for h in header]
        try:
            idx = next(i for i, h in enumerate(lowered) if h in ("source", "reviewer"))
        except StopIteration:
            continue
        internal_rows = [
            (row[0], row[idx])
            for row in rows
            if idx < len(row) and "internal code review" in row[idx].lower()
        ]
        if not internal_rows:
            continue
        missing = [(n, v) for n, v in internal_rows if "superpowers" not in v.lower()]
        if missing:
            listed = "\n".join(f"    row {n}: {v!r}" for n, v in missing[:8])
            return (
                "[hook:block-consolidate-verify-format-mismatch] BLOCKED — AI "
                f"Review Summary has {len(missing)} internal-review row(s) whose "
                "Source cell is missing the literal substring `superpowers`:\n"
                f"{listed}\n\n"
                "verify_consolidate.py's 'Superpowers inclusion' check greps the "
                "Source column for `superpowers` (case-insensitive substring) to "
                "confirm the internal code-reviewer's findings are physically in "
                "the table. Plain `Internal Code Review` alone does not match.\n\n"
                "Use `Internal Code Review (superpowers)` in the Source cell for "
                "every row sourced from the internal reviewer.\n\n"
                "Bypass (only if you are certain): ALLOW_CONSOLIDATE_VERIFY_FORMAT=1 <command>"
            )
    return None


def main() -> int:
    runtime, command = read_input()
    if not runtime or not command:
        return 0

    if (
        os.environ.get("ALLOW_CONSOLIDATE_VERIFY_FORMAT") == "1"
        or "ALLOW_CONSOLIDATE_VERIFY_FORMAT=1" in command
    ):
        return 0
    if not is_comment_or_review_post(command):
        return 0

    for body in extract_bodies(command):
        reason = check_internal_review_headings(body)
        if reason:
            emit_block(runtime, reason)
        reason = check_summary_superpowers_source(body)
        if reason:
            emit_block(runtime, reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
