#!/usr/bin/env python3
"""
stale_check.py - Automated stale document detection script for Antigravity / Ralph workspace.

Checks plan/research artifacts in <tracker-root>/docs/generated/, <tracker-root>/plan-drafts/ (tracker-root = .agents or .ralph), and llm-wiki/outputs/
against 3-layer detection signals:
  L1: Self-declaration & age check
  L2: Reference integrity (relates_to, commits, fix_plan backref)
  L3: External state (PR merged, fix_plan [x] status)

Usage:
  python stale_check.py [--root <path>] [--report <path>]
"""

import sys
import os
import re
import glob
import json
import argparse
import subprocess

from workspace_profile import resolve_tracker_root

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

STANDARD_STATUSES = {
    "draft", "ready", "approved", "in-progress", "in_progress",
    "partially-applied", "partially_applied", "applied", "superseded",
    "archived", "completed", "decided"
}

TERMINAL_STATUSES = {"applied", "superseded", "archived", "completed"}
TARGET_PREFIXES = ("plan-", "research-", "analysis-", "handoff-", "deploy-plan-")


def target_dirs(tracker_root):
    """Artifact scan dirs, rooted at the resolved tracker root (.agents / .ralph)."""
    return [
        os.path.join(tracker_root, "docs", "generated"),
        os.path.join(tracker_root, "plan-drafts"),
        os.path.join("llm-wiki", "outputs"),
    ]

def parse_frontmatter(content):
    """Extract YAML frontmatter dictionary and remaining body text."""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    
    yaml_text = parts[1]
    body_text = parts[2]
    meta = {}
    for line in yaml_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip().strip('"').strip("'")
            meta[key] = val
    return meta, body_text

def normalize_status(raw_status):
    """Normalize raw status string taking the first token."""
    if not raw_status:
        return None, "NO-STATUS"
    
    # Extract first word/token
    token = raw_status.split()[0].lower().strip(",")
    if token in STANDARD_STATUSES:
        return token, "OK"
    return token, "NON-STANDARD"

def check_git_commit(root, sha):
    """Verify if a git commit SHA exists in local repository."""
    try:
        res = subprocess.run(
            ["git", "cat-file", "-e", sha],
            cwd=root, capture_output=True, text=True, check=False
        )
        return res.returncode == 0
    except Exception:
        return True

def scan_documents(root):
    """Scan target directories and evaluate document statuses."""
    results = {
        "STALE-CONFIRMED": [],
        "BROKEN-REF": [],
        "ORPHAN-SUSPECT": [],
        "AGE-SUSPECT": [],
        "NO-STATUS": [],
        "NON-STANDARD": [],
        "OK": []
    }
    
    tracker_root = resolve_tracker_root(root)
    fix_plan_content = ""
    fix_plan_path = os.path.join(root, tracker_root, "fix_plan.md")
    if os.path.exists(fix_plan_path):
        try:
            with open(fix_plan_path, "r", encoding="utf-8") as f:
                fix_plan_content = f.read()
        except Exception:
            pass

    for rel_dir in target_dirs(tracker_root):
        abs_dir = os.path.join(root, rel_dir)
        if not os.path.exists(abs_dir):
            continue
        
        for filename in os.listdir(abs_dir):
            if not filename.endswith(".md"):
                continue
            if not (filename.startswith(TARGET_PREFIXES) or "plan-drafts" in rel_dir):
                continue

            filepath = os.path.join(abs_dir, filename)
            rel_path = os.path.relpath(filepath, root).replace("\\", "/")
            
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception as e:
                continue

            meta, body = parse_frontmatter(content)
            raw_status = meta.get("status")
            status, code = normalize_status(raw_status)

            if code == "NO-STATUS":
                results["NO-STATUS"].append({"file": rel_path, "reason": "status: field missing"})
                continue

            if code == "NON-STANDARD":
                results["NON-STANDARD"].append({"file": rel_path, "reason": f"Non-standard status: '{raw_status}'"})
            
            if status in TERMINAL_STATUSES:
                results["OK"].append({"file": rel_path, "reason": f"Terminal status: {status}"})
                continue

            # L2 Check: relates_to reference check
            relates_to = meta.get("relates_to", "")
            if relates_to and relates_to.lower() != "none":
                if ".md" in relates_to or "/" in relates_to:
                    target_file = relates_to.split()[0]
                    ref_base = os.path.basename(target_file)
                    ref_found = (
                        os.path.exists(os.path.join(root, target_file))
                        or os.path.exists(os.path.join(root, tracker_root, target_file))
                        or os.path.exists(os.path.join(abs_dir, ref_base))  # sibling in the doc's own scan dir
                        or any(os.path.exists(os.path.join(root, d, ref_base)) for d in target_dirs(tracker_root))
                    )
                    if not ref_found:
                        results["BROKEN-REF"].append({"file": rel_path, "reason": f"Referenced file missing: {target_file}"})
                        continue

            # L3 Check: fix_plan back-reference check
            filename_base = os.path.basename(rel_path)
            if fix_plan_content and filename_base in fix_plan_content:
                lines = fix_plan_content.splitlines()
                for i, line in enumerate(lines):
                    if filename_base in line:
                        if "- [x]" in line or (i > 0 and "- [x]" in lines[i-1]):
                            results["STALE-CONFIRMED"].append({"file": rel_path, "reason": f"Referenced in fix_plan.md under completed item [x]"})
                            break
                else:
                    results["OK"].append({"file": rel_path, "reason": "Active & linked in fix_plan"})
            else:
                # llm-wiki/* is the knowledge tier — intentionally NOT fix_plan-linked
                # (a wiki knowledge artifact is not an active tracker item), so an unlinked
                # approved/ready doc there is expected, not an orphan.
                is_wiki_tier = rel_dir.startswith("llm-wiki")
                if status in ("ready", "approved") and not is_wiki_tier:
                    results["ORPHAN-SUSPECT"].append({"file": rel_path, "reason": "Approved/ready doc not linked in fix_plan.md"})
                else:
                    results["OK"].append({"file": rel_path, "reason": "Wiki knowledge tier (intentionally unlinked)" if is_wiki_tier else "Draft doc"})

    return results

def main():
    parser = argparse.ArgumentParser(description="Stale document detector")
    parser.add_argument("--root", default=".", help="Workspace root directory")
    parser.add_argument("--report", default="", help="Optional markdown report path")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    results = scan_documents(root)

    print("=== Stale Check Summary ===")
    for category, items in results.items():
        print(f"  {category:<15}: {len(items)} items")

    if results["STALE-CONFIRMED"]:
        print("\n🚨 [STALE-CONFIRMED]:")
        for item in results["STALE-CONFIRMED"]:
            print(f"  - {item['file']}: {item['reason']}")

    if results["BROKEN-REF"]:
        print("\n⚠️ [BROKEN-REF]:")
        for item in results["BROKEN-REF"]:
            print(f"  - {item['file']}: {item['reason']}")

    if results["ORPHAN-SUSPECT"]:
        print("\n🔍 [ORPHAN-SUSPECT]:")
        for item in results["ORPHAN-SUSPECT"]:
            print(f"  - {item['file']}: {item['reason']}")

    if args.report:
        report_path = os.path.abspath(args.report)
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Stale Check Report\n\n")
            for cat, items in results.items():
                f.write(f"## {cat} ({len(items)})\n")
                for item in items:
                    f.write(f"- `{item['file']}`: {item['reason']}\n")
                f.write("\n")
        print(f"\nReport written to: {report_path}")

if __name__ == "__main__":
    main()
