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


def register_tasks_to_fix_plan(md_path: Path, profile: dict):
    """Extract '- [ ]' action items from artifact and append to current workspace fix_plan.md."""
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post-Creation Ingest & Task Extraction")
    parser.add_argument("md_path", help="Path to created markdown plan/research artifact")
    parser.add_argument("--workspace", help="Workspace profile override (must exist in config.json profiles)")
    args = parser.parse_args()

    md_file = Path(args.md_path).resolve()
    if not md_file.exists():
        print(f"Error: Target file {md_file} does not exist", file=sys.stderr)
        sys.exit(1)

    profile = get_profile(workspace_name=args.workspace, target_path=str(md_file))
    print(f"Active Post-Ingest Profile: {profile['workspace_name']}")

    ingest_md_to_qdrant(md_file, profile)
    register_tasks_to_fix_plan(md_file, profile)
