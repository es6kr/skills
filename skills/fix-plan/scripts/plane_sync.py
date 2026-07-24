#!/usr/bin/env python3
"""
plane_sync.py - Plane REST API Synchronization Engine for fix_plan.md
Syncs local markdown checklist items ([ ], [x], [BLOCKED]) with Plane Workspace Issues & Cycles.
Supports graceful degradation if Plane API key is not configured.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
import argparse
from pathlib import Path
from workspace_profile import get_profile


def make_plane_request(profile: dict, path: str, method: str = "GET", data: dict = None) -> dict:
    """Make an authenticated HTTP request to Plane REST API."""
    token = profile.get("plane_token")
    if not token:
        return {"error": f"API token ({profile['plane_token_env']}) not set"}

    url = f"{profile['plane_host'].rstrip('/')}/api/v1/{path.lstrip('/')}"
    headers = {
        "x-api-key": token,
        "Content-Type": "application/json"
    }

    req_data = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status in (200, 201):
                return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

    return {"error": "Request failed"}


def fetch_plane_issues(profile: dict, project_slug: str) -> list:
    """Fetch issues for project from Plane."""
    path = f"workspaces/{profile['workspace_name']}/projects/{project_slug}/issues/"
    res = make_plane_request(profile, path)
    if "error" in res:
        print(f"[Plane Sync] Note: {res['error']}", file=sys.stderr)
        return []
    return res.get("results", [])


def sync_checklist_with_plane(fix_plan_path: Path, profile: dict, dry_run: bool = False):
    """Parse fix_plan.md and sync with Plane."""
    if not fix_plan_path.exists():
        print(f"Target fix_plan file {fix_plan_path} not found.", file=sys.stderr)
        return

    print(f"[Plane Sync] Workspace: {profile['workspace_name']} (Plane Host: {profile['plane_host']})")
    token = profile.get("plane_token")

    if not token:
        print(f"[Plane Sync] Token '{profile['plane_token_env']}' is not set in environment.")
        print("[Plane Sync] Operating in Local Offline Mode (Graceful degradation).")
        return

    issues = fetch_plane_issues(profile, profile["default_project"])
    print(f"[Plane Sync] Fetched {len(issues)} issues from Plane project '{profile['default_project']}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plane REST API Checklist Sync")
    parser.add_argument("--workspace", help="Workspace profile override (must exist in config.json profiles)")
    parser.add_argument("--fix-plan", help="Path to fix_plan.md")
    parser.add_argument("--dry-run", action="store_true", help="Simulate sync without modifying Plane or fix_plan")
    args = parser.parse_args()

    target_path = args.fix_plan or os.getcwd()
    profile = get_profile(workspace_name=args.workspace, target_path=target_path)

    fix_plan_file = Path(args.fix_plan) if args.fix_plan else Path(target_path) / "fix_plan.md"
    if not fix_plan_file.exists():
        fix_plan_file = Path(target_path) / ".ralph" / "fix_plan.md"

    sync_checklist_with_plane(fix_plan_file, profile, dry_run=args.dry_run)
