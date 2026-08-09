#!/usr/bin/env python3
"""
plane_sync.py - Plane REST API sync engine for fix_plan.md / checklist.md workspaces

Mirrors the GitHub PR/Issue sync rules in fix-plan/sync.md, applied in reverse
(Plane -> fix_plan marker instead of fix_plan -> Plane): it parses the index
lines a workspace's Phase-3 migration produces (see
`plan-plane-backlog-migration.md` "Index화 규칙"),

    - [<marker>] [<IDENT>-<seq>] <title> -> Plane (<issue URL>)

queries each referenced Plane issue's current state, resolves that state's
`group` (a second API call -- the issue-detail response only carries the
state as a bare UUID, not an inline `state_detail` object), and updates the
marker when the issue is `completed` (-> `[x]`) or `cancelled` (->
`[BLOCKED:P2:external]`) — the same two terminal states GitHub sync acts on
(PR MERGED / PR CLOSED-without-merge). Non-terminal states (backlog /
unstarted / started) and API errors leave the line untouched, matching
sync.md's "no change on OPEN" / "no change on API error" rules.
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


INDEX_LINE_RE = re.compile(
    r'^(?P<indent>\s*)-\s+\[(?P<marker>[^\]]*)\]\s+\[(?P<ident>[A-Z]+-\d+)\]\s+(?P<title>.+?)\s+'
    r'→\s+Plane\s+\((?P<url>https://[^\s)]+)\)(?P<rest>.*)$'
)

PLANE_URL_RE = re.compile(
    r'https://[^/]+/(?P<workspace>[^/]+)/projects/(?P<project>[0-9a-f-]{36})/issues/(?P<issue>[0-9a-f-]{36})'
)

# Plane state_detail.group -> fix_plan marker. Only terminal states are mapped
# (mirrors sync.md's GitHub MERGED/CLOSED-without-merge rules); non-terminal
# groups (backlog/unstarted/started) are intentionally absent so compute_updates()
# leaves those lines unchanged.
STATE_TO_MARKER = {
    "completed": "[x]",
    "cancelled": "[BLOCKED:P2:external]",
}


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


def parse_index_lines(lines: list) -> list:
    """Extract Plane index-line matches from a fix_plan.md/checklist.md line list.

    Returns one dict per matched line: {line_no, match, url_match}. Lines that
    don't match the `- [<marker>] [<IDENT>-<seq>] <title> -> Plane (<url>)`
    shape, or whose URL doesn't parse as a Plane workspace/project/issue URL,
    are skipped (untouched by compute_updates())."""
    matches = []
    for i, line in enumerate(lines):
        m = INDEX_LINE_RE.match(line)
        if not m:
            continue
        url_m = PLANE_URL_RE.search(m.group("url"))
        if not url_m:
            continue
        matches.append({"line_no": i, "match": m, "url_match": url_m})
    return matches


def fetch_issue_state(profile: dict, workspace: str, project: str, issue: str) -> dict:
    """Fetch a single Plane issue's detail. The real API v1 response carries
    the issue's current state as a bare state-UUID in `state` (no inline
    `state_detail` object) -- resolve the group via fetch_state_group()."""
    path = f"workspaces/{workspace}/projects/{project}/issues/{issue}/"
    return make_plane_request(profile, path)


def fetch_state_group(profile: dict, workspace: str, project: str, state_id: str) -> dict:
    """Resolve a Plane state UUID to its detail (for its `group`:
    backlog/unstarted/started/completed/cancelled)."""
    path = f"workspaces/{workspace}/projects/{project}/states/{state_id}/"
    return make_plane_request(profile, path)


def compute_updates(lines: list, profile: dict) -> list:
    """Compute the set of line replacements sync would apply, without writing
    anything. Returns [{line_no, old, new}, ...] for lines whose Plane issue
    is completed/cancelled and whose current marker doesn't already match."""
    updates = []
    # A project's states are a small fixed set (Todo/In Progress/Done/...),
    # so many tracked issues share the same state id -- resolve each state
    # id's group at most once per sync run instead of once per issue.
    state_group_cache = {}
    for entry in parse_index_lines(lines):
        um = entry["url_match"]
        issue_data = fetch_issue_state(profile, um["workspace"], um["project"], um["issue"])
        if "error" in issue_data:
            # sync.md rule: never change state on API error.
            continue
        state_id = issue_data.get("state")
        if not state_id:
            continue
        cache_key = (um["project"], state_id)
        if cache_key not in state_group_cache:
            state_data = fetch_state_group(profile, um["workspace"], um["project"], state_id)
            state_group_cache[cache_key] = None if "error" in state_data else state_data.get("group")
        state_group = state_group_cache[cache_key]
        new_marker = STATE_TO_MARKER.get(state_group)
        if new_marker is None:
            # Non-terminal state (backlog/unstarted/started) -> no change.
            continue
        current_marker = f"[{entry['match'].group('marker')}]"
        if current_marker == new_marker:
            continue
        old_line = lines[entry["line_no"]]
        new_line = old_line.replace(current_marker, new_marker, 1)
        updates.append({"line_no": entry["line_no"], "old": old_line, "new": new_line})
    return updates


def sync_checklist_with_plane(fix_plan_path: Path, profile: dict, dry_run: bool = False):
    """Parse fix_plan_path's Plane index lines, resolve each referenced issue's
    current state via the Plane API, and (unless --dry-run) rewrite the lines
    whose issue is now completed/cancelled. Reports the change count either way
    (sync.md "Report format" convention)."""
    if not fix_plan_path.exists():
        print(f"Target fix_plan file {fix_plan_path} not found.", file=sys.stderr)
        return

    print(f"[Plane Sync] Workspace: {profile['workspace_name']} (Plane Host: {profile['plane_host']})")
    token = profile.get("plane_token")

    if not token:
        print(f"[Plane Sync] Token '{profile['plane_token_env']}' is not set in environment.")
        print("[Plane Sync] Operating in Local Offline Mode (Graceful degradation).")
        return

    original_bytes = fix_plan_path.read_bytes()
    lines = original_bytes.decode("utf-8").splitlines(keepends=True)
    # splitlines(keepends=True) preserves each line's own newline so we can
    # write the file back verbatim except for the replaced marker text.
    stripped_lines = [l.rstrip("\n") for l in lines]
    updates = compute_updates(stripped_lines, profile)

    if not updates:
        print("[Plane Sync] No changes (0 index lines moved to completed/cancelled).")
        return

    for u in updates:
        print(f"[Plane Sync] line {u['line_no'] + 1}: {u['old'].strip()!r} -> {u['new'].strip()!r}")

    if dry_run:
        print(f"[Plane Sync] --dry-run: {len(updates)} line(s) would change. No write performed.")
        return

    # compute_updates() above made one HTTP request per linked issue, so an
    # editor could have changed the tracker during that window. Re-read and
    # compare against the original snapshot before writing — an unconditional
    # write from the stale snapshot would silently discard any such edit.
    if fix_plan_path.read_bytes() != original_bytes:
        print(
            f"[Plane Sync] Aborted: {fix_plan_path} changed on disk since sync started "
            "(concurrent edit detected). Re-run sync.",
            file=sys.stderr,
        )
        return

    for u in updates:
        newline = "\n" if lines[u["line_no"]].endswith("\n") else ""
        lines[u["line_no"]] = u["new"] + newline

    # Atomic write: write to a sibling temp file, then rename over the target
    # so a crash/interrupt mid-write never leaves a partially-written tracker.
    tmp_path = fix_plan_path.with_name(fix_plan_path.name + ".tmp")
    tmp_path.write_text("".join(lines), encoding="utf-8")
    tmp_path.replace(fix_plan_path)
    print(f"[Plane Sync] {len(updates)} line(s) updated in {fix_plan_path}.")


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
