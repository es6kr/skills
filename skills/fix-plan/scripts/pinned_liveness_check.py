#!/usr/bin/env python3
"""
pinned_liveness_check.py -- Pinned-mission liveness check for fix_plan.md / checklist.md

Checks whether a tracker's pinned header block cites backing items that have
all resolved ([x], or moved to `## Completed`), and if so, surfaces a
candidate next-mission suggestion. This script never writes to the tracker
-- it only reports. The calling fix-plan flow (see flowchart.md
"Pinned-mission liveness check") is responsible for confirming any refresh
with the user via AskUserQuestion before editing the pinned block.

Citation convention (opt-in, an HTML comment appended to a pinned bullet
line that already has a **bold label**):

    <!-- pinned-backing: todo:"<substring>", deep:"<substring>" -->

Each citation points at a tracker section:
    todo:"X"  -> the `## TODO` section (or `## Completed`, once it moved)
    deep:"X"  -> the `## Deep Tasks` section (or `## Completed`)

A citation resolves True when the line containing the substring is found
under its home section prefixed with `- [x]`, or is found (with any prefix)
under `## Completed`. It resolves False when found under its home section
still `[ ]` / `[BLOCKED...]`. It resolves None (unknown) when the substring
is not found anywhere -- reported separately, never silently treated as
resolved.

A pinned bullet with NO `pinned-backing` marker is reported as
"unmonitored" and excluded from candidate detection. There is no fuzzy-text
fallback by design: guessing at citations from prose risks false-positive
"this mission is done" claims, which is worse than under-reporting. This is
a new, opt-in convention -- existing pinned blocks adopt it line by line as
they are next edited.
"""

import argparse
import json
import re
import sys
from pathlib import Path

SECTION_RE = re.compile(r'^##\s+(.+?)\s*$')
CITATION_ITEM_RE = re.compile(r'(\w+):"([^"]*)"')
MARKER_RE = re.compile(r'<!--\s*pinned-backing:\s*(.*?)\s*-->')
MISSION_LABEL_RE = re.compile(r'^\s*>?\s*-\s+\*\*(.+?)\*\*\s*:')
DEEP_TASK_LABEL_RE = re.compile(r'\*\*(.+?)\*\*')

HOME_SECTION = {"todo": "TODO", "deep": "Deep Tasks"}
PINNED_KEY = "__pinned__"


def split_sections(text):
    """Return {section_name: [line, ...]} for every top-level '## X' block,
    plus a PINNED_KEY entry for the leading lines before the first '##'
    heading (where a tracker's pinned header block lives)."""
    sections = {PINNED_KEY: []}
    current = PINNED_KEY
    for line in text.splitlines():
        m = SECTION_RE.match(line)
        if m:
            current = m.group(1).strip()
            sections.setdefault(current, [])
            continue
        sections[current].append(line)
    return sections


def extract_missions(pinned_lines):
    """Find pinned bullet lines with a bold label and an optional
    pinned-backing citation marker."""
    missions = []
    for line in pinned_lines:
        label_m = MISSION_LABEL_RE.search(line)
        if not label_m:
            continue
        marker_m = MARKER_RE.search(line)
        citations = []
        if marker_m:
            citations = list(CITATION_ITEM_RE.findall(marker_m.group(1)))
        missions.append({
            "label": label_m.group(1).strip(),
            "citations": citations,
            "monitored": bool(citations),
        })
    return missions


def _line_status(line):
    stripped = line.strip()
    if stripped.startswith("- [x]"):
        return "x"
    if stripped.startswith("- [ ]"):
        return "open"
    if stripped.startswith("- [BLOCKED"):
        return "blocked"
    return None


def resolve_citation(kind, substr, sections):
    """Resolve one citation to True (done) / False (still open) / None
    (substring not found anywhere -- unknown, not a false positive)."""
    home = HOME_SECTION.get(kind)
    if home is None:
        return None
    for line in sections.get(home, []):
        if substr in line:
            status = _line_status(line)
            if status == "x":
                return True
            if status in ("open", "blocked"):
                return False
            # Matched a prose line (e.g. a `Why`/`How` body quoting the same
            # words) rather than the item's own checkbox line -- keep
            # scanning for the actual item line instead of deciding here.
    for line in sections.get("Completed", []):
        if substr in line:
            return True
    return None


def evaluate_mission(mission, sections):
    if not mission["monitored"]:
        return {**mission, "status": "unmonitored"}
    results = [resolve_citation(kind, sub, sections) for kind, sub in mission["citations"]]
    if any(r is False for r in results):
        status = "open"
    elif any(r is None for r in results):
        status = "unknown"
    else:
        status = "resolved"
    return {**mission, "status": status, "citation_results": results}


def find_next_mission_candidate(sections, roadmap_path=None):
    """Candidate source order: (a) the workspace's declared roadmap doc's
    first unchecked top-level checklist item, (b) the highest-priority open
    `## Deep Tasks` entry (P0 first, skipping already-[PROMOTED] entries)."""
    if roadmap_path:
        try:
            text = Path(roadmap_path).read_text(encoding="utf-8")
        except OSError:
            text = ""
        m = re.search(r'^\s*-\s+\[\s\]\s+(.+)$', text, re.MULTILINE)
        if m:
            return {"source": "roadmap", "path": str(roadmap_path), "candidate": m.group(1).strip()}

    deep_lines = sections.get("Deep Tasks", [])
    for prio in ("P0", "P1", "P2", "P3"):
        for line in deep_lines:
            if f"[BLOCKED:{prio}:" not in line:
                continue
            if "[PROMOTED]" in line:
                continue
            m = DEEP_TASK_LABEL_RE.search(line)
            if m:
                return {"source": "deep-tasks", "priority": prio, "candidate": m.group(1).strip()}
    return None


def run(tracker_path, roadmap_path=None):
    text = Path(tracker_path).read_text(encoding="utf-8")
    sections = split_sections(text)
    missions = extract_missions(sections.get(PINNED_KEY, []))
    evaluated = [evaluate_mission(m, sections) for m in missions]
    resolved = [m for m in evaluated if m["status"] == "resolved"]
    report = {
        "tracker": str(tracker_path),
        "missions": evaluated,
        "resolved_count": len(resolved),
    }
    if resolved:
        report["next_mission_candidate"] = find_next_mission_candidate(sections, roadmap_path)
    return report


def main():
    parser = argparse.ArgumentParser(description="Pinned-mission liveness check for fix_plan.md/checklist.md")
    parser.add_argument("tracker", help="Path to fix_plan.md or checklist.md")
    parser.add_argument(
        "--roadmap-doc",
        help="Optional roadmap markdown file; its first unchecked '- [ ]' line "
             "becomes the next-mission candidate when a pinned mission resolves"
    )
    parser.add_argument("--json", action="store_true", help="Emit the full report as JSON")
    args = parser.parse_args()

    report = run(args.tracker, args.roadmap_doc)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    for m in report["missions"]:
        print(f"[{m['status']}] {m['label']}")
    print(f"resolved_count={report['resolved_count']}")
    if "next_mission_candidate" in report:
        print(f"next_mission_candidate={report['next_mission_candidate']}")


if __name__ == "__main__":
    main()
