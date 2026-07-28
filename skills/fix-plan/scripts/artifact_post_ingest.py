#!/usr/bin/env python3
"""
artifact_post_ingest.py - Post-Creation Ingest Module for Plan & Research Artifacts
Ingests newly created markdown artifacts (plan-*.md, research-*.md) into the active
workspace's Qdrant collection and registers extracted checklist items to fix_plan.md.
Executes qdrant-import via uvx (fastembed runtime).
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from workspace_profile import get_profile


def ingest_md_to_qdrant(md_path: Path, profile: dict):
    """Trigger qdrant-import.py via uvx in markdown mode for the active workspace."""
    qdrant_import_script = Path.home() / ".gemini" / "config" / "skills" / "es6kr" / "scripts" / "qdrant-import.py"
    if not qdrant_import_script.exists():
        qdrant_import_script = Path.home() / ".claude" / "skills" / "es6kr" / "scripts" / "qdrant-import.py"

    if not qdrant_import_script.exists():
        print(f"WARN: qdrant-import.py script not found at {qdrant_import_script}", file=sys.stderr)
        return False

    cmd = [
        "uvx", "--from", "fastembed", "--with", "requests", "python",
        str(qdrant_import_script),
        "--source", "md",
        "--md-path", str(md_path),
        "--qdrant-url", profile["qdrant_url"],
        "--collection", profile["qdrant_wiki_collection"]
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode == 0:
            print(f"[Post-Ingest] Successfully indexed {md_path.name} to Qdrant ({profile['qdrant_wiki_collection']})")
            return True
        else:
            print(f"[Post-Ingest] Qdrant import note: {res.stderr.strip() or res.stdout.strip()}", file=sys.stderr)
    except Exception as e:
        print(f"[Post-Ingest] Error running Qdrant import: {e}", file=sys.stderr)

    return False


def resolve_fix_plan_path(explicit: str = None, target_path: str = None) -> Path:
    """Resolve the tracker file: explicit --fix-plan override, else <cwd>/fix_plan.md,
    else <cwd>/.ralph/fix_plan.md, else <cwd>/checklist.md (non-Ralph workspaces)."""
    if explicit:
        return Path(explicit)

    base = Path(target_path or os.getcwd())
    candidate = base / "fix_plan.md"
    if candidate.exists():
        return candidate
    candidate = base / ".ralph" / "fix_plan.md"
    if candidate.exists():
        return candidate
    return base / "checklist.md"


def register_tasks_to_fix_plan(md_path: Path, profile: dict, fix_plan_path: Path = None):
    """Extract '- [ ]' action items from artifact and append to the workspace tracker
    (fix_plan.md / checklist.md) under '## Progress', skipping items already present."""
    if not md_path.exists():
        return

    try:
        content = md_path.read_text(encoding="utf-8")
    except Exception:
        return

    action_items = []
    for line in content.splitlines():
        line_s = line.strip()
        if line_s.startswith("- [ ]") and len(line_s) > 7:
            item_text = line_s[5:].strip()
            action_items.append(item_text)

    if not action_items:
        return

    print(f"[Post-Ingest] Extracted {len(action_items)} action items from {md_path.name}")

    if fix_plan_path is None or not fix_plan_path.exists():
        print(f"[Post-Ingest] Tracker file not found ({fix_plan_path}) - skipping registration. "
              f"Extracted items were only logged above.", file=sys.stderr)
        return

    try:
        tracker_content = fix_plan_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[Post-Ingest] Failed to read tracker file {fix_plan_path}: {e}", file=sys.stderr)
        return

    tracker_lines = tracker_content.splitlines()

    # Idempotency: skip items whose exact "- [ ] {text}" line already exists anywhere in the tracker.
    existing = {ln.strip() for ln in tracker_lines}
    new_items = [text for text in action_items if f"- [ ] {text}" not in existing]

    if not new_items:
        print(f"[Post-Ingest] All {len(action_items)} extracted items already present in {fix_plan_path.name} - nothing to register")
        return

    # Insert new items at the end of the '## Progress' section (before the next '## ' header).
    progress_idx = next((i for i, ln in enumerate(tracker_lines) if ln.strip() == "## Progress"), None)
    if progress_idx is None:
        print(f"[Post-Ingest] No '## Progress' section found in {fix_plan_path.name} - skipping registration "
              f"({len(new_items)} item(s) not registered).", file=sys.stderr)
        return

    insert_at = len(tracker_lines)
    for i in range(progress_idx + 1, len(tracker_lines)):
        if tracker_lines[i].startswith("## "):
            insert_at = i
            break

    # Trim blank lines immediately before the boundary so we can re-insert a
    # single separating blank line after the new items (when a following
    # section header exists).
    trim_at = insert_at
    while trim_at > progress_idx + 1 and tracker_lines[trim_at - 1].strip() == "":
        trim_at -= 1

    new_lines = [f"- [ ] {text}" for text in new_items]
    separator = [""] if insert_at < len(tracker_lines) else []
    updated_lines = tracker_lines[:trim_at] + new_lines + separator + tracker_lines[insert_at:]

    try:
        fix_plan_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    except Exception as e:
        print(f"[Post-Ingest] Failed to write tracker file {fix_plan_path}: {e}", file=sys.stderr)
        return

    print(f"[Post-Ingest] Registered {len(new_items)} new item(s) to {fix_plan_path} ## Progress "
          f"({len(action_items) - len(new_items)} already present, skipped)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post-Creation Ingest & Task Extraction")
    parser.add_argument("md_path", help="Path to created markdown plan/research artifact")
    parser.add_argument("--workspace", help="Workspace profile override (must exist in config.json profiles)")
    parser.add_argument("--fix-plan", help="Path to fix_plan.md / checklist.md (default: auto-resolve from cwd)")
    args = parser.parse_args()

    md_file = Path(args.md_path).resolve()
    if not md_file.exists():
        print(f"Error: Target file {md_file} does not exist", file=sys.stderr)
        sys.exit(1)

    profile = get_profile(workspace_name=args.workspace, target_path=str(md_file))
    print(f"Active Post-Ingest Profile: {profile['workspace_name']}")

    fix_plan_file = resolve_fix_plan_path(explicit=args.fix_plan, target_path=os.getcwd())

    ingest_md_to_qdrant(md_file, profile)
    register_tasks_to_fix_plan(md_file, profile, fix_plan_file)
