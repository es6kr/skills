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
from workspace_profile import get_profile, resolve_tracker_root


# plane.es6.kr sits behind Cloudflare, which 403s the default `Python-urllib`
# User-Agent. A browser-like User-Agent header is required — same constant as
# plane_create_comment.py, the in-repo precedent that already clears the WAF.
UA = "Mozilla/5.0 (plane-backlog)"

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

# fix_plan P0-P3 marker <-> Plane native priority. Self-contained duplicate of
# plane_client.py's mapping (skills/plane-backlog/scripts/) rather than a
# cross-directory import -- this repo's established pattern for the
# plane_create_issue.py pair is duplicate-copy-plus-sync-tests, not shared
# imports across skill directories (see plan-plane-done-state-and-priority-
# mapping.md Risk table "Duplicate Script Drift").
MARKER_TO_PRIORITY = {"P0": "urgent", "P1": "high", "P2": "medium", "P3": "low"}
PRIORITY_TO_MARKER = {native: marker for marker, native in MARKER_TO_PRIORITY.items()}
VALID_PLANE_PRIORITIES = frozenset(MARKER_TO_PRIORITY.values()) | {"none"}

MARKER_PRIORITY_RE = re.compile(r'\bP([0-3])\b')


def normalize_priority(value):
    """Accept a P0-P3 tag (case-insensitive) or a direct Plane priority value
    and return the Plane native value. Raises ValueError on anything else."""
    if not value:
        return "none"
    upper = value.strip().upper()
    if upper in MARKER_TO_PRIORITY:
        return MARKER_TO_PRIORITY[upper]
    lower = value.strip().lower()
    if lower in VALID_PLANE_PRIORITIES:
        return lower
    raise ValueError(
        f"Unrecognized priority {value!r} -- expected P0-P3 "
        f"(case-insensitive) or {sorted(VALID_PLANE_PRIORITIES)}"
    )


def priority_to_marker(native_priority):
    """Reverse of normalize_priority: Plane native value -> P0-P3 marker.
    Returns None for 'none' or an unrecognized value (no fix_plan marker
    corresponds to Plane's 'none' priority)."""
    return PRIORITY_TO_MARKER.get((native_priority or "").strip().lower())


def extract_local_priority(marker_text):
    """Pull a P0-P3 tag out of a fix_plan marker string (e.g.
    'BLOCKED:P1:external' -> 'high') and return its native Plane priority.
    Returns None when the marker carries no P-tag (plain ' ' or 'x' markers,
    or a BLOCKED marker without a priority segment) -- such lines are outside
    detect_priority_drift()'s scope, not a match failure."""
    m = MARKER_PRIORITY_RE.search(marker_text)
    if not m:
        return None
    return MARKER_TO_PRIORITY[f"P{m.group(1)}"]


def make_plane_request(profile: dict, path: str, method: str = "GET", data: dict = None) -> dict:
    """Make an authenticated HTTP request to Plane REST API."""
    token = profile.get("plane_token")
    if not token:
        return {"error": f"API token ({profile['plane_token_env']}) not set"}

    url = f"{profile['plane_host'].rstrip('/')}/api/v1/{path.lstrip('/')}"
    headers = {
        "x-api-key": token,
        "Content-Type": "application/json",
        "User-Agent": UA
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
        # Key includes project because fetch_state_group() calls the
        # project-scoped states/ endpoint -- resolving a state_id requires
        # knowing which project it belongs to.
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


def detect_priority_drift(lines: list, profile: dict) -> list:
    """Report-only: compare each tracked issue's local P0-P3 tag (if any)
    against its live Plane `priority` field. Returns
    [{line_no, ident, local_priority, plane_priority}, ...] for every
    mismatch. Never mutates fix_plan.md or Plane -- per the 2026-08-20 Fable
    audit (plan-plane-done-state-and-priority-mapping.md §7-3), a
    first-adoption priority-sync run stays advisory-only until a human
    confirms the direction, since existing local markers may carry local
    triage judgment Plane doesn't know about."""
    drifts = []
    for entry in parse_index_lines(lines):
        marker_text = entry["match"].group("marker")
        local_priority = extract_local_priority(marker_text)
        if local_priority is None:
            continue
        um = entry["url_match"]
        issue_data = fetch_issue_state(profile, um["workspace"], um["project"], um["issue"])
        if "error" in issue_data:
            # sync.md rule: never report on API error -- same as compute_updates().
            continue
        plane_priority = (issue_data.get("priority") or "none").lower()
        if plane_priority == local_priority:
            continue
        drifts.append({
            "line_no": entry["line_no"],
            "ident": entry["match"].group("ident"),
            "local_priority": local_priority,
            "plane_priority": plane_priority,
        })
    return drifts


def fetch_project_states(profile: dict, workspace: str, project: str) -> list:
    """GET all states for a project (Todo/In Progress/Done/... plus their
    `group`). Resolving which state UUID belongs to the `completed` group
    requires this list -- PATCHing an issue's state needs the state's own id,
    not its group name."""
    path = f"workspaces/{workspace}/projects/{project}/states/"
    res = make_plane_request(profile, path)
    if "error" in res:
        return []
    return res.get("results", []) if isinstance(res, dict) else res


def find_state_id_by_group(states: list, group: str) -> str:
    """Return the first state id whose `group` matches, or None."""
    for s in states:
        if s.get("group") == group:
            return s.get("id")
    return None


def transition_issue_to_done(profile: dict, workspace: str, project: str, issue: str) -> dict:
    """PATCH a Plane issue's state to the project's `completed`-group state.

    This is the ONLY state-mutation this module performs on a Plane issue --
    DELETE is never called (Plane Issue DELETE Prohibition & Done State
    Preservation Rule, HARD STOP: deleted issues break inbound wiki/tracker
    links; a local item finishing must always transition its Plane issue to
    Done, never remove it). Returns {"error": ...} if the project has no
    completed-group state or the PATCH fails; otherwise the updated issue
    payload."""
    states = fetch_project_states(profile, workspace, project)
    done_state_id = find_state_id_by_group(states, "completed")
    if not done_state_id:
        return {"error": f"No completed-group state found for project {project}"}
    path = f"workspaces/{workspace}/projects/{project}/issues/{issue}/"
    return make_plane_request(profile, path, method="PATCH", data={"state": done_state_id})


def compute_local_to_plane_updates(lines: list, profile: dict) -> list:
    """The reverse leg of compute_updates(): for index lines whose LOCAL
    marker is already `[x]` but the linked Plane issue isn't yet in the
    `completed` group, queue a Done-transition. Never DELETEs -- a Plane
    issue that falls behind its local item stays open until this (or a
    human) explicitly transitions it via transition_issue_to_done()."""
    updates = []
    state_group_cache = {}
    for entry in parse_index_lines(lines):
        marker_text = entry["match"].group("marker")
        if marker_text != "x":
            continue
        um = entry["url_match"]
        issue_data = fetch_issue_state(profile, um["workspace"], um["project"], um["issue"])
        if "error" in issue_data:
            continue
        state_id = issue_data.get("state")
        if not state_id:
            continue
        cache_key = (um["project"], state_id)
        if cache_key not in state_group_cache:
            state_data = fetch_state_group(profile, um["workspace"], um["project"], state_id)
            state_group_cache[cache_key] = None if "error" in state_data else state_data.get("group")
        if state_group_cache[cache_key] == "completed":
            continue
        updates.append({
            "line_no": entry["line_no"],
            "ident": entry["match"].group("ident"),
            "workspace": um["workspace"],
            "project": um["project"],
            "issue": um["issue"],
        })
    return updates


def sync_checklist_with_plane(fix_plan_path: Path, profile: dict, dry_run: bool = False, push_done: bool = False):
    """Parse fix_plan_path's Plane index lines, resolve each referenced issue's
    current state via the Plane API, and (unless --dry-run) rewrite the lines
    whose issue is now completed/cancelled. Reports the change count either way
    (sync.md "Report format" convention).

    Also always prints a priority-drift report (report-only, never written --
    see detect_priority_drift()'s docstring). When push_done=True, additionally
    transitions any Plane issue whose linked local item is already `[x]` but
    whose Plane state isn't yet `completed` to Done (never DELETE; see
    transition_issue_to_done()) -- respects --dry-run same as the primary sync."""
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

    drifts = detect_priority_drift(stripped_lines, profile)
    if drifts:
        print(f"[Plane Sync] Priority drift detected on {len(drifts)} line(s) (report-only, not applied):")
        for d in drifts:
            print(
                f"[Plane Sync]   line {d['line_no'] + 1} [{d['ident']}]: "
                f"local={d['local_priority']} vs Plane={d['plane_priority']}"
            )

    if push_done:
        push_updates = compute_local_to_plane_updates(stripped_lines, profile)
        if not push_updates:
            print("[Plane Sync] --push-done: no local [x] items pending a Done transition.")
        elif dry_run:
            for u in push_updates:
                print(f"[Plane Sync] --push-done (dry-run): [{u['ident']}] would transition to Done.")
        else:
            for u in push_updates:
                result = transition_issue_to_done(profile, u["workspace"], u["project"], u["issue"])
                if "error" in result:
                    print(f"[Plane Sync] --push-done: [{u['ident']}] failed: {result['error']}", file=sys.stderr)
                else:
                    print(f"[Plane Sync] --push-done: [{u['ident']}] transitioned to Done.")

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
    parser.add_argument(
        "--push-done", action="store_true",
        help="Transition Plane issues to Done when their linked local item is already [x] "
             "but Plane hasn't caught up (never DELETEs; respects --dry-run)",
    )
    args = parser.parse_args()

    target_path = args.fix_plan or os.getcwd()
    profile = get_profile(workspace_name=args.workspace, target_path=target_path)

    fix_plan_file = Path(args.fix_plan) if args.fix_plan else Path(target_path) / "fix_plan.md"
    if not fix_plan_file.exists():
        fix_plan_file = Path(target_path) / resolve_tracker_root(target_path) / "fix_plan.md"

    sync_checklist_with_plane(fix_plan_file, profile, dry_run=args.dry_run, push_done=args.push_done)
