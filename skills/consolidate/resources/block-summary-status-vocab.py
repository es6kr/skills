#!/usr/bin/env python3
"""PreToolUse hook: block an AI Review Summary POST whose findings table uses a
Status vocabulary outside the contract in `consolidate/post.md`.

Why this exists
---------------
`post.md` fixes the findings-table Status column to exactly five values:

    🟢 Fixed (commit <sha>) / 🔴 Pending / 🟡 Deferred (author follow-up)
    / 🟢 Deferred (no action) / ⚪ Rejected — <reason>

and carries a HARD STOP ("Prohibit Using Verified Status") requiring a valid,
unfixed, in-diff finding to be `🔴 Pending` from the start. That rule existed as
prose only, and the same class of violation recurred four times — `Verified`,
`🟢 Verified`, `✅ Accept`, `✅ VALID` — each time by promoting the
`receiving-code-review` judgement frame (accept/reject, valid/rejected) into the
published Status column. The two are different axes: the frame decides whether a
finding is worth acting on, the Status column encodes whether it blocks merge.

The damage is not cosmetic. `post.md` derives the merge recommendation FROM the
Status column ("any 🔴 Pending → Hold"), so a self-invented value zeroes the
Pending count and flips the conclusion to "no merge blocker" — which is how the
4th occurrence shipped a Hold-worthy PR as merge-ready.

`verify_consolidate.py` did not catch any of the four: it checks row counts,
reviewer counts, SHAs and ordering, but never the Status values themselves.
This guard closes that gap at the POST, before the comment exists.

I/O contract (cross-platform, mirrors block-noncompliant-review-comment.sh)
--------------------------------------------------------------------------
  - Claude Code: stdin {tool_name, tool_input.command}; block = exit 2 + stderr
  - Antigravity: stdin {toolCall.name, toolCall.args.*}; block = stdout
                 {"decision":"deny","reason":...} + exit 0

Bypass (per-command only, never session-wide):
    ALLOW_SUMMARY_STATUS_VOCAB=1 <command>
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

SUMMARY_MARKER = "AI Review Summary"

# The five contract values (post.md "Allowed Status values").
# The leading emoji is the documented form but optional here: the failure class
# is an invented *word* (VALID / Accept / Verified / ...), not a missing emoji.
ALLOWED_STATUS = (
    re.compile(r"^(🟢\s*)?Fixed\b"),
    re.compile(r"^(🔴\s*)?Pending\b"),
    re.compile(r"^(🟡\s*|🟢\s*)?Deferred\b"),
    re.compile(r"^(⚪\s*)?Rejected\b"),
)

# Vocabulary that has actually shipped in past violations.
FORBIDDEN_TOKENS = re.compile(
    r"\b(VALID|Accept(ed)?|Verified|Unverified|Out of scope)\b", re.IGNORECASE
)


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


def is_comment_post(command: str) -> bool:
    """Does this command publish/patch a PR or issue comment?"""
    if re.search(r"\bgh\s+(pr|issue)\s+comment\b", command):
        return True
    # gh api ... issues/comments/<id>  (POST or PATCH)
    if re.search(r"\bgh\s+api\b", command) and re.search(
        r"(issues|pulls)/(comments/)?\d*/?comments?\b|issues/comments/\d+", command
    ):
        return True
    return False


def extract_bodies(command: str) -> list[str]:
    """Collect every candidate comment body reachable from the command line."""
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
    """Return [(header_cells, data_rows)] for tables that look like findings tables
    (at least one row whose first cell is a bare number)."""
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


def main() -> int:
    runtime, command = read_input()
    if not runtime or not command:
        return 0

    if os.environ.get("ALLOW_SUMMARY_STATUS_VOCAB") == "1" or "ALLOW_SUMMARY_STATUS_VOCAB=1" in command:
        return 0
    if not is_comment_post(command):
        return 0

    for body in extract_bodies(command):
        if SUMMARY_MARKER not in body:
            continue
        for header, rows in find_findings_tables(body):
            lowered = [h.lower() for h in header]
            try:
                idx = next(i for i, h in enumerate(lowered) if h == "status")
            except StopIteration:
                emit_block(
                    runtime,
                    "[hook:block-summary-status-vocab] BLOCKED — AI Review Summary findings "
                    "table has no `Status` column.\n"
                    f"  header: {' | '.join(header)}\n\n"
                    "post.md fixes the column name to `Status` and its values to exactly five:\n"
                    "  🟢 Fixed (commit <sha>) / 🔴 Pending / 🟡 Deferred (author follow-up)\n"
                    "  / 🟢 Deferred (no action) / ⚪ Rejected — <reason>\n\n"
                    "Renaming it (`Verdict`, `Verdict + verification`, ...) is how the judgement\n"
                    "frame from receiving-code-review leaks into the published column. Those are\n"
                    "separate axes: the frame decides whether a finding is valid, Status encodes\n"
                    "whether it blocks merge — and post.md derives the merge recommendation from\n"
                    "Status, so a renamed column silently flips the conclusion.\n\n"
                    "Bypass (only if you are certain): ALLOW_SUMMARY_STATUS_VOCAB=1 <command>",
                )
            bad = []
            for row in rows:
                cell = row[idx] if idx < len(row) else ""
                plain = re.sub(r"[*`_]", "", cell).strip()
                if not any(rx.match(plain) for rx in ALLOWED_STATUS):
                    bad.append((row[0], cell))
            if bad:
                listed = "\n".join(f"    row {n}: {v!r}" for n, v in bad[:8])
                more = f"\n    ... and {len(bad) - 8} more" if len(bad) > 8 else ""
                emit_block(
                    runtime,
                    "[hook:block-summary-status-vocab] BLOCKED — AI Review Summary Status column "
                    f"carries {len(bad)} value(s) outside the post.md contract:\n"
                    f"{listed}{more}\n\n"
                    "Allowed values (post.md 'Allowed Status values'):\n"
                    "  🟢 Fixed (commit <sha>)   — fix landed, SHA mandatory\n"
                    "  🔴 Pending                — valid, in-diff, not yet fixed\n"
                    "  🟡 Deferred (author follow-up)\n"
                    "  🟢 Deferred (no action)\n"
                    "  ⚪ Rejected — <one-line reason>\n\n"
                    "A valid finding inside the diff that is not yet fixed is 🔴 Pending from the\n"
                    "start — that is the 'Prohibit Using Verified Status' HARD STOP. Reproduction\n"
                    "evidence belongs in an evidence column, not in Status.\n\n"
                    "This matters beyond wording: post.md derives the merge recommendation FROM\n"
                    "this column (any 🔴 Pending → Hold), so a self-invented value zeroes the\n"
                    "Pending count and flips the verdict to 'no merge blocker'.\n\n"
                    "Bypass (only if you are certain): ALLOW_SUMMARY_STATUS_VOCAB=1 <command>",
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
