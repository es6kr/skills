#!/usr/bin/env python3
"""fa-inbox-triage.py - Parse improvements.md, enumerate un-triaged entries, and promote/drain.

Skeleton kept unchanged from plan-fa-staging-inbox-integration.md Sec.2.2 per
roadmap-followup-fa-prep-20261010.md Sec.3.2 -- the FA-promotion schema-header
emission (`<!-- fa: class=... count=N count_agy=X count_claude=Y env=... -->`)
and the drain/prune logic are explicitly deferred to Phase 3 (not implemented
here; see Phase 1-2 scope in next-roadmap-decision.md).
"""
import re

ENTRY_RE = re.compile(r"^##\s+\[(.*?)\]\s+(.*?)\n(.*?)(?=\n##\s+\[|\Z)", re.DOTALL | re.MULTILINE)


TAG_NEEDS_REVIEW_RE = re.compile(r"^[ \t]*-[ \t]+\*\*Tag\*\*:[ \t]*\[NEEDS_REVIEW\]", re.MULTILINE)


def scan_inbox(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    entries = []
    for match in ENTRY_RE.finditer(content):
        header_type, title, body = match.groups()
        if TAG_NEEDS_REVIEW_RE.search(body):
            entries.append({"type": header_type, "title": title, "body": body.strip()})
    return entries
