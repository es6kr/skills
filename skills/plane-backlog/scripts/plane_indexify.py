#!/usr/bin/env python3
"""plane_indexify.py — reconcile tracker items with Plane issues and index them.

Turns a local ``fix_plan.md`` / ``checklist.md`` item whose content already
lives in Plane into a one-line index entry::

    - [BLOCKED:P2:external] [INFRA-22] PR 60 review findings → Plane (<url>) *(note)*

The manual version of this reconciliation is slow and, more importantly, easy to
get wrong in a way that loses text. The safety rules that made it survivable are
encoded here rather than left to per-session discipline:

  * **Boilerplate normalization** — issues migrated in bulk carry a trailing
    "(fix_plan Phase 3 <migration-note>, YYYY-MM-DD)" marker whose note words are
    written in the tracker's own language. Comparing raw titles makes every
    migrated issue look like a local-only divergence.
  * **Local-only content gate** — a block is only collapsed when every line of
    its local body is already present in the Plane description. Anything else is
    reported as ``local-only`` and left untouched. This is the guard that keeps
    the conversion lossless.
  * **Line-integrity check + atomic replace** — the tracker is edited by other
    sessions concurrently, so each write re-reads the file, verifies the exact
    block it planned to replace is still there, and swaps the file via
    ``os.replace``. A block that moved is skipped, never overwritten blind.

Standard library only.

Usage::

    plane_indexify.py --tracker fix_plan.md --project <uuid>            # report
    plane_indexify.py --tracker fix_plan.md --project <uuid> --apply    # convert
"""

import argparse
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plane_client import PlaneClient, html_to_text  # noqa: E402

# Trailing marker stamped on issues created by the bulk migration. Left in place
# it makes an otherwise identical title score as a mismatch.
#
# The marker's note words are locale-specific, so they are matched with the
# Unicode-aware \w class instead of being hardcoded as literals — keeping this
# public source free of one workspace's language while still matching its data
# (opensource.md "public repo locale-specific patterns"). Override with
# PLANE_BOILERPLATE_RE when a tracker stamps a differently shaped marker.
DEFAULT_BOILERPLATE_RE = (
    r"\s*[(（]?\s*fix[_ ]plan\s+phase\s*3\s+index\w*\s+\w+\s*"
    r"[,，]?\s*\d{4}\s*[-.]?\s*\d{2}\s*[-.]?\s*\d{2}\s*[)）]?\s*$"
)
BOILERPLATE_RE = re.compile(
    os.environ.get("PLANE_BOILERPLATE_RE", DEFAULT_BOILERPLATE_RE), re.IGNORECASE
)
ITEM_RE = re.compile(r"^(?P<indent>\s*)- \[(?P<marker>[^\]]*)\]\s+(?P<title>.+?)\s*$")
ALREADY_INDEXED_RE = re.compile(r"^\s*- \[[^\]]*\]\s+\[[A-Z][A-Z0-9]*-\d+\]")


def normalize(text):
    """Lowercased, boilerplate-free, whitespace-collapsed form used for matching."""
    text = BOILERPLATE_RE.sub("", text or "")
    text = re.sub(r"\*\([^)]*\)\*", " ", text)          # trailing italic annotations
    text = re.sub(r"\[[^\]]*\]\([^)]*\)", " ", text)    # markdown links
    text = re.sub(r"[`*_~]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def similarity(a, b):
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def parse_blocks(lines):
    """Yield unindexed item blocks as dicts of start/end/indent/marker/title/body.

    A block runs from its ``- [marker] title`` header to the last following line
    that is indented deeper than the header (its sub-bullets and notes).
    """
    blocks = []
    for i, line in enumerate(lines):
        match = ITEM_RE.match(line)
        if not match or ALREADY_INDEXED_RE.match(line):
            continue
        indent = len(match.group("indent"))
        end = i
        for j in range(i + 1, len(lines)):
            nxt = lines[j]
            if not nxt.strip():
                # blank line only continues the block if deeper content follows
                if any(
                    lines[k].strip() and len(lines[k]) - len(lines[k].lstrip()) > indent
                    for k in range(j + 1, min(j + 3, len(lines)))
                ):
                    continue
                break
            if len(nxt) - len(nxt.lstrip()) <= indent:
                break
            end = j
        blocks.append(
            {
                "start": i,
                "end": end,
                "indent": match.group("indent"),
                "marker": match.group("marker"),
                "title": match.group("title"),
                "body": [lines[k] for k in range(i + 1, end + 1)],
            }
        )
    return blocks


LABEL_RE = re.compile(r"^\s*\*\*[^*]+\*\*\s*[:：]\s*")


def local_only_lines(body, plane_text):
    """Body lines whose content is absent from the Plane description.

    Bullet markers and bold labels (``**Why**:``, ``**How to apply**:``) are
    stripped first — they are tracker-side scaffolding that never appears in the
    Plane description, and comparing them verbatim flags every well-formed item
    as local-only.
    """
    haystack = normalize(plane_text)
    missing = []
    for raw in body:
        stripped = re.sub(r"^\s*[-*+]\s*", "", raw)
        stripped = LABEL_RE.sub("", stripped)
        needle = normalize(stripped)
        if len(needle) < 8:
            continue  # too short to compare meaningfully
        if needle not in haystack:
            missing.append(raw.strip())
    return missing


def build_index_line(block, issue, identifier, url, note):
    ident = "%s-%s" % (identifier, issue.get("sequence_id"))
    title = BOILERPLATE_RE.sub("", issue.get("name") or block["title"]).strip()
    return "%s- [%s] [%s] %s → Plane (%s) *(%s)*" % (
        block["indent"],
        block["marker"],
        ident,
        title,
        url,
        note,
    )


def apply_patches(tracker, patches):
    """Re-read, verify each block is unmoved, then rewrite the file atomically."""
    with open(tracker, encoding="utf-8") as fh:
        current = fh.read().split("\n")

    applied, conflicts = [], []
    for patch in sorted(patches, key=lambda p: p["start"], reverse=True):
        window = current[patch["start"] : patch["end"] + 1]
        if window != patch["old_block"]:
            conflicts.append(patch["ident"])
            continue
        current[patch["start"] : patch["end"] + 1] = [patch["new_line"]]
        applied.append(patch["ident"])

    if applied:
        tmp = tracker + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(current))
        os.replace(tmp, tracker)
    return applied, conflicts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tracker", required=True, help="fix_plan.md / checklist.md path")
    parser.add_argument("--project", action="append", required=True, help="Plane project id (repeatable)")
    parser.add_argument("--apply", action="store_true", help="write the conversions (default: report only)")
    parser.add_argument("--min-score", type=float, default=0.82, help="minimum title similarity (default 0.82)")
    parser.add_argument(
        "--note",
        default="indexed to Plane — details live in the Plane description",
        help="italic annotation appended to each converted line (pass a localized string to match the tracker)",
    )
    parser.add_argument("--cache", help="issue cache path (skips refetch on re-run)")
    parser.add_argument("--force", action="store_true", help="convert even when local-only body lines remain")
    args = parser.parse_args(argv)

    with open(args.tracker, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    blocks = parse_blocks(lines)

    client = PlaneClient(cache_path=args.cache)
    issues, identifiers = [], {}
    for project_id in args.project:
        project = client.request("workspaces/%s/projects/%s/" % (client.profile["workspace_slug"], project_id))
        identifiers[project_id] = project.get("identifier", "ISSUE")
        for issue in client.list_issues(project_id):
            issue["_project"] = project_id
            issues.append(issue)

    matched, blocked, unmatched = [], [], []
    used = set()
    for block in blocks:
        best, best_score = None, 0.0
        for issue in issues:
            if issue["id"] in used:
                continue
            score = similarity(block["title"], issue.get("name", ""))
            if score > best_score:
                best, best_score = issue, score
        if not best or best_score < args.min_score:
            unmatched.append((block["title"][:70], round(best_score, 2)))
            continue

        plane_text = "%s\n%s" % (best.get("name", ""), html_to_text(best.get("description_html")))
        missing = local_only_lines(block["body"], plane_text)
        project_id = best["_project"]
        ident = "%s-%s" % (identifiers[project_id], best.get("sequence_id"))

        if missing and not args.force:
            blocked.append((ident, block["title"][:60], len(missing)))
            continue

        used.add(best["id"])
        matched.append(
            {
                "ident": ident,
                "start": block["start"],
                "end": block["end"],
                "old_block": lines[block["start"] : block["end"] + 1],
                "new_line": build_index_line(
                    block, best, identifiers[project_id], client.issue_url(project_id, best["id"]), args.note
                ),
                "score": round(best_score, 2),
            }
        )

    print("blocks scanned : %d" % len(blocks))
    print("matched        : %d" % len(matched))
    print("local-only gate: %d (body text not yet in Plane — not converted)" % len(blocked))
    print("unmatched      : %d" % len(unmatched))
    for ident, title, count in blocked:
        print("  ! %-14s %-60s %d local-only line(s)" % (ident, title, count))
    for item in matched:
        print("  = %-14s score %.2f  %s" % (item["ident"], item["score"], item["new_line"].strip()[:100]))

    # Near-misses make an all-unmatched result interpretable: a top score far
    # below the threshold means "no counterpart exists", while a cluster just
    # under it means the threshold is the thing to reconsider.
    near = sorted(unmatched, key=lambda u: u[1], reverse=True)[:5]
    if near:
        print("  ~ closest unmatched (threshold %.2f):" % args.min_score)
        for title, score in near:
            print("      %.2f  %s" % (score, title))

    if not args.apply:
        print("\n(report only — pass --apply to write)")
        return 0

    applied, conflicts = apply_patches(args.tracker, matched)
    print("\napplied   : %d" % len(applied))
    print("conflicts : %d %s" % (len(conflicts), conflicts or ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
