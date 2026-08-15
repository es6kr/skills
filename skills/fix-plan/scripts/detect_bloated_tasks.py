#!/usr/bin/env python3
"""detect_bloated_tasks.py — detect bloated completed items and unmarked residuals
in the ACTIVE sections of fix_plan.md / checklist.md.

What it flags:
1. Active Work Sections (everything before a '## Completed' header) are scanned.
2. '[x]' completed markers still sitting in an active section (move candidates).
3. Indented sub-bullet residual items missing a '- [ ]' checkbox (format-fix candidates).

Locale tokens: non-English tracker markers (e.g. a localized completed-section
header) live in the git-ignored data/locale-patterns.json. The PUBLIC repo ships
English-only; a local data file adds locale support. Absent data file => English-only
behaviour (never crashes).

Usage:
    python detect_bloated_tasks.py [--file path/to/fix_plan.md]
"""

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_locale_tokens():
    """Load optional locale-specific parser tokens from the git-ignored data/ dir.

    Returns empty (English-only) defaults when the data file is absent — the PUBLIC
    repo ships English-only; a local data/locale-patterns.json adds locale tokens.
    """
    defaults = {
        "completed_section_markers": [],
        "active_section_markers": [],
        "residual_keywords": [],
    }
    data_file = Path(__file__).resolve().parent / "data" / "locale-patterns.json"
    if data_file.exists():
        try:
            loaded = json.loads(data_file.read_text(encoding="utf-8"))
            for key in defaults:
                value = loaded.get(key)
                if isinstance(value, list):
                    defaults[key] = [str(v) for v in value]
        except Exception:
            pass
    return defaults


def build_residual_pattern(residual_keywords):
    """Indented '- ' bullets starting with a residual keyword (locale) or 'Step X' /
    'Phase N' (English) — the marker-agnostic residual detector."""
    alternatives = [re.escape(k) for k in residual_keywords] + [r"Step\s+[A-Z0-9]", r"Phase\s+[0-9]"]
    return re.compile(r"^\s{2,}-\s+(" + "|".join(alternatives) + r")")


def detect_bloated_tasks(file_path: Path):
    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}", file=sys.stderr)
        return False, [], []

    tokens = load_locale_tokens()
    completed_markers = tokens["completed_section_markers"]
    active_markers = tokens["active_section_markers"]
    residual_pattern = build_residual_pattern(tokens["residual_keywords"])

    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    in_active_section = False
    in_completed_section = False

    completed_in_active = []  # (line_no, line_text)
    unmarked_residuals = []   # (line_no, line_text)

    for idx, line in enumerate(lines, start=1):
        line_strip = line.strip()

        # Section-header detection
        if line.startswith("## "):
            header_title = line[3:].strip().lower()
            if "completed" in header_title or any(m in header_title for m in completed_markers):
                in_completed_section = True
                in_active_section = False
            elif ("fable" in header_title or "residual" in header_title
                  or any(m in line for m in active_markers)):
                in_active_section = True
                in_completed_section = False

        if in_completed_section:
            continue

        # 1. Completed '[x]' items still inside an active section
        if re.search(r"^\s*-\s*\[[xX]\]", line):
            completed_in_active.append((idx, line))

        # 2. Indented residual items missing a '- [ ]' checkbox
        if in_active_section and residual_pattern.search(line):
            if not re.search(r"^\s*-\s*\[[ xX]\]", line_strip):
                unmarked_residuals.append((idx, line))

    return True, completed_in_active, unmarked_residuals


def main():
    parser = argparse.ArgumentParser(description="Detect bloated/unmarked tasks in fix_plan.md active sections.")
    parser.add_argument("--file", help="Path to fix_plan.md or checklist.md", default=None)
    args = parser.parse_args()

    if args.file:
        target_path = Path(args.file)
    else:
        # Default fallback locations (tracker root resolved: .agents / .ralph / auto-detect)
        from workspace_profile import resolve_tracker_root
        default_1 = Path.cwd() / resolve_tracker_root() / "fix_plan.md"
        default_2 = Path.cwd() / "fix_plan.md"
        default_3 = Path.cwd() / "checklist.md"
        target_path = default_1 if default_1.exists() else (default_2 if default_2.exists() else default_3)

    print(f"[Scanning] {target_path}")
    ok, completed_list, unmarked_list = detect_bloated_tasks(target_path)

    if not ok:
        sys.exit(1)

    print(f"\nAudit Results for: {target_path.name}")
    print("=" * 60)

    if completed_list:
        print(f"[FOUND {len(completed_list)}] Completed items still in ACTIVE sections (move to ## Completed):")
        for line_no, line in completed_list:
            clean_text = re.sub(r"^\s*-\s*\[[xX]\]\s*", "", line.strip())
            print(f"  L{line_no}: {clean_text[:100]}")
    else:
        print("OK: No completed '[x]' items left in active sections.")

    print("-" * 60)

    if unmarked_list:
        print(f"[FOUND {len(unmarked_list)}] Unmarked residual items missing '- [ ]' checkbox:")
        for line_no, line in unmarked_list:
            print(f"  L{line_no}: {line.strip()[:100]}")
    else:
        print("OK: All active sub-residuals have explicit '- [ ]' markers.")

    print("=" * 60)

    if completed_list or unmarked_list:
        sys.exit(1)
    else:
        print("Clean status! No bloated or unmarked tasks detected.")
        sys.exit(0)


if __name__ == "__main__":
    main()
