#!/usr/bin/env python3
"""
fable_queue_replenish.py - Fable target task candidate scanner for Antigravity / Ralph.

Scans candidate sources for Fable replenishment:
  S1: Fable section remaining items ([BLOCKED:P*:selfable])
  S2: <tracker-root>/plan-drafts/ stub files (tracker-root = .agents or .ralph)
  S3: Unlinked draft / ready artifacts in <tracker-root>/docs/generated/ and llm-wiki/outputs/
  S4: STALE-CONFIRMED items from stale_check.py

Usage:
  python fable_queue_replenish.py [--root <path>]
"""

import sys
import os
import re
import argparse

from workspace_profile import resolve_tracker_root

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def parse_frontmatter(content):
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    meta = {}
    for line in parts[1].splitlines():
        line = line.strip()
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip().strip('"').strip("'")
    return meta

def scan_fable_candidates(root):
    candidates = {
        "S1_Fable_Section_Remaining": [],
        "S2_Plan_Drafts_Stubs": [],
        "S3_Orphan_Draft_Artifacts": [],
        "S4_Stale_Confirmed": []
    }

    tracker_root = resolve_tracker_root(root)
    fix_plan_path = os.path.join(root, tracker_root, "fix_plan.md")
    fix_plan_content = ""
    if os.path.exists(fix_plan_path):
        try:
            with open(fix_plan_path, "r", encoding="utf-8") as f:
                fix_plan_content = f.read()
        except Exception:
            pass

    # S1: Scan fix_plan [BLOCKED:P*:selfable]
    if fix_plan_content:
        for line in fix_plan_content.splitlines():
            if "- [BLOCKED:" in line and ":selfable]" in line and "- [x]" not in line:
                candidates["S1_Fable_Section_Remaining"].append(line.strip())

    # S2: Scan <tracker_root>/plan-drafts/
    drafts_dir = os.path.join(root, tracker_root, "plan-drafts")
    if os.path.exists(drafts_dir):
        for fn in os.listdir(drafts_dir):
            if fn.endswith(".md"):
                fp = os.path.join(drafts_dir, fn)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        meta = parse_frontmatter(f.read())
                    status = meta.get("status", "draft")
                    if status != "completed":
                        candidates["S2_Plan_Drafts_Stubs"].append(f"{tracker_root}/plan-drafts/{fn} (status: {status})")
                except Exception:
                    pass

    # S3: Scan unlinked draft/ready artifacts
    for rel_dir in [os.path.join(tracker_root, "docs", "generated"), os.path.join("llm-wiki", "outputs")]:
        abs_dir = os.path.join(root, rel_dir)
        if not os.path.exists(abs_dir):
            continue
        for fn in os.listdir(abs_dir):
            if fn.endswith(".md") and (fn.startswith("plan-") or fn.startswith("research-")):
                fp = os.path.join(abs_dir, fn)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        meta = parse_frontmatter(f.read())
                    status = meta.get("status", "")
                    if status in ("draft", "ready") and fn not in fix_plan_content:
                        rel_path = os.path.relpath(fp, root).replace("\\", "/")
                        candidates["S3_Orphan_Draft_Artifacts"].append(f"{rel_path} (status: {status})")
                except Exception:
                    pass

    return candidates

def main():
    parser = argparse.ArgumentParser(description="Fable candidate scanner")
    parser.add_argument("--root", default=".", help="Workspace root directory")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    candidates = scan_fable_candidates(root)

    print("=== Fable Queue Replenishment Candidates ===")
    for source, items in candidates.items():
        print(f"\n📂 {source} ({len(items)} items):")
        for item in items[:10]:
            print(f"  - {item}")
        if len(items) > 10:
            print(f"  ... and {len(items) - 10} more items.")

if __name__ == "__main__":
    main()
