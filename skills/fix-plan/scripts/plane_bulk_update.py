#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plane Bulk Update Script with Diff-based Conflict Protection & Rate Limit Handling
Synchronizes Priorities and Dates from fix_plan.md to Plane (plane.dgs.ai.kr)
Features:
- 3-Way Diff Analysis (FILL, NO-OP, CONFLICT)
- Strict Overwrite Protection: Never modifies existing non-empty Plane values in safe mode
- Detailed Diff & Conflict Report
- Optional --force-conflicts flag for explicit conflict resolution
- Rate-limiting (HTTP 429) exponential backoff & inter-request throttling
"""

import os
import sys
import re
import time
import json
import argparse
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')

DEFAULT_FIX_PLAN = r"C:\Users\DAEGUNSOFT\ghq\github.com\daegunsoftDev\.agents\fix_plan.md"
BASE_URL = "https://plane.dgs.ai.kr/api/v1/workspaces/daegunsoftdev"

PRIORITY_MAP = {
    "P0": "urgent",
    "P1": "high",
    "P2": "medium",
    "P3": "low"
}

def get_api_key():
    key = os.environ.get("DGS_PLANE_API_KEY")
    if not key:
        try:
            import winreg
            reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
            key, _ = winreg.QueryValueEx(reg, "DGS_PLANE_API_KEY")
            winreg.CloseKey(reg)
        except Exception:
            pass
    return key

def parse_fix_plan(fix_plan_path):
    if not os.path.exists(fix_plan_path):
        print(f"Error: fix_plan.md not found at {fix_plan_path}")
        return {}

    with open(fix_plan_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    issue_map = {}
    alt_issue_pattern = re.compile(r'\[([A-Z]+)-(\d+)\]')
    alt_prio_pattern = re.compile(r'\[(?:BLOCKED:)?(P[0-3])(?::[a-z]+)?\]')
    date_pattern = re.compile(r'(\d{4}-\d{2}-\d{2})')

    current_section = ""
    for line in lines:
        if line.startswith("## "):
            current_section = line.strip()
            continue

        m = alt_issue_pattern.search(line)
        if m:
            ident = m.group(1)
            seq = int(m.group(2))
            key = f"{ident}-{seq}"

            p_match = alt_prio_pattern.search(line)
            prio = PRIORITY_MAP.get(p_match.group(1), None) if p_match else None

            d_match = date_pattern.search(line)
            date_val = d_match.group(1) if d_match else None

            is_done = line.strip().startswith("- [x]") or "Completed" in current_section

            if key not in issue_map or (prio and not issue_map[key]["priority"]):
                issue_map[key] = {
                    "ident": ident,
                    "seq": seq,
                    "priority": prio,
                    "is_done": is_done,
                    "date": date_val,
                    "raw_line": line.strip()[:90]
                }

    return issue_map

def fetch_plane_projects_and_issues(headers):
    req = urllib.request.Request(f"{BASE_URL}/projects/", headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        projects = data.get('results', data if isinstance(data, list) else [])

    plane_issues = {}
    for p in projects:
        p_id = p['id']
        p_ident = p['identifier']
        i_req = urllib.request.Request(f"{BASE_URL}/projects/{p_id}/issues/?limit=100", headers=headers)
        try:
            with urllib.request.urlopen(i_req) as i_resp:
                i_data = json.loads(i_resp.read().decode('utf-8'))
                issues = i_data.get('results', i_data if isinstance(i_data, list) else [])
                for iss in issues:
                    seq = iss.get('sequence_id')
                    key = f"{p_ident}-{seq}"
                    plane_issues[key] = {
                        "project_id": p_id,
                        "issue_id": iss.get('id'),
                        "name": iss.get('name'),
                        "priority": iss.get('priority'),
                        "target_date": iss.get('target_date'),
                        "start_date": iss.get('start_date'),
                        "state": iss.get('state'),
                        "updated_at": iss.get('updated_at')
                    }
        except Exception as e:
            print(f"Error fetching issues for project {p_ident}: {e}")

    return plane_issues

def update_plane_issue(project_id, issue_id, payload, headers, max_retries=3):
    url = f"{BASE_URL}/projects/{project_id}/issues/{issue_id}/"
    data_bytes = json.dumps(payload).encode('utf-8')

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method='PATCH')
            with urllib.request.urlopen(req) as resp:
                time.sleep(0.35)  # Throttling to stay well within rate limit
                return resp.status in (200, 204)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_sec = 2.0 * (attempt + 1)
                time.sleep(wait_sec)
                continue
            else:
                raise e
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(1.0)
    return False

def main():
    parser = argparse.ArgumentParser(description="Diff-based & Conflict-Safe Plane Bulk Update")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Preview diff without applying")
    parser.add_argument("--force-conflicts", action="store_true", default=False, help="Force overwrite even if Plane has existing conflicting value")
    parser.add_argument("--fix-plan", default=DEFAULT_FIX_PLAN, help="Path to fix_plan.md")
    parser.add_argument("--project", help="Filter to specific project (INFRA, AIAUTO, DTWEB, OPS)")
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("Error: DGS_PLANE_API_KEY environment variable not found.")
        sys.exit(1)

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    print("1. Parsing fix_plan.md metadata...")
    plan_meta = parse_fix_plan(args.fix_plan)
    print(f"   -> Found {len(plan_meta)} Plane issue references in fix_plan.md.")

    print("2. Fetching live state from plane.dgs.ai.kr...")
    plane_issues = fetch_plane_projects_and_issues(headers)
    print(f"   -> Fetched {len(plane_issues)} live issues from Plane.")

    safe_fills = []
    conflicts = []
    no_ops = []

    for key, p_info in plane_issues.items():
        if args.project and not key.startswith(args.project + "-"):
            continue

        meta = plan_meta.get(key)
        if not meta:
            continue

        patch_body = {}
        conflict_details = []

        # --- Priority Diff ---
        local_prio = meta["priority"]
        live_prio = p_info["priority"] or "none"

        if local_prio:
            if live_prio in ("none", "", None):
                patch_body["priority"] = local_prio
            elif live_prio == local_prio:
                pass
            else:
                conflict_details.append({
                    "field": "priority",
                    "live": live_prio,
                    "local": local_prio
                })
                if args.force_conflicts:
                    patch_body["priority"] = local_prio

        # --- Target Date Diff ---
        local_date = meta["date"]
        live_date = p_info["target_date"]

        if local_date:
            if live_date in (None, ""):
                patch_body["target_date"] = local_date
            elif live_date == local_date:
                pass
            else:
                conflict_details.append({
                    "field": "target_date",
                    "live": live_date,
                    "local": local_date
                })
                if args.force_conflicts:
                    patch_body["target_date"] = local_date

        if conflict_details and not args.force_conflicts:
            conflicts.append({
                "key": key,
                "name": p_info["name"],
                "conflicts": conflict_details,
                "project_id": p_info["project_id"],
                "issue_id": p_info["issue_id"]
            })

        if patch_body:
            safe_fills.append({
                "key": key,
                "project_id": p_info["project_id"],
                "issue_id": p_info["issue_id"],
                "name": p_info["name"],
                "patch": patch_body
            })
        elif not conflict_details:
            no_ops.append(key)

    print("\n" + "=" * 90)
    print("3. DIFF & CONFLICT ANALYSIS REPORT")
    print("=" * 90)
    print(f"Total Evaluated: {len(plane_issues)} issues | Safe Fills: {len(safe_fills)} | Conflicts: {len(conflicts)} | Up-to-Date: {len(no_ops)}")
    print("-" * 90)

    if conflicts:
        print("\n⚠️  DETECTED CONFLICTS (Overwrites BLOCKED by default):")
        for c in conflicts:
            conf_str = ", ".join([f"{cf['field']}: live='{cf['live']}' vs local='{cf['local']}'" for cf in c["conflicts"]])
            status_tag = "FORCE OVERWRITE" if args.force_conflicts else "PROTECTED / SKIPPED"
            print(f"  [CONFLICT] [{c['key']}] {c['name'][:35]:<35} | {conf_str} -> {status_tag}")
    else:
        print("\n✔  No conflicting overwrites detected.")

    if safe_fills:
        print(f"\n🚀  SAFE UPDATES (Applying to empty fields): {len(safe_fills)} items")
        for s in safe_fills:
            patch_str = ", ".join([f"{k}='{v}'" for k, v in s["patch"].items()])
            print(f"  [FILL]     [{s['key']}] {s['name'][:40]:<40} | + {patch_str}")

    print("=" * 90)

    if args.dry_run:
        print(f"\n[DRY-RUN] Execution completed. No changes written to Plane.")
        if conflicts and not args.force_conflicts:
            print(f"Note: {len(conflicts)} conflicting fields were protected from overwrite.")
        return

    if not safe_fills:
        print("\nAll target issues are already synchronized!")
        return

    print(f"\n4. Applying {len(safe_fills)} conflict-safe updates to Plane API...")
    success = 0
    for s in safe_fills:
        try:
            ok = update_plane_issue(s["project_id"], s["issue_id"], s["patch"], headers)
            if ok:
                success += 1
                print(f"  ✔ [{s['key']}] Applied {s['patch']}")
            else:
                print(f"  ✖ [{s['key']}] Failed")
        except Exception as e:
            print(f"  ✖ [{s['key']}] Error: {e}")

    print(f"\nFinished: {success}/{len(safe_fills)} safe updates successfully committed to Plane.")
    if conflicts and not args.force_conflicts:
        print(f"Protected {len(conflicts)} items from unintended overwrite.")

if __name__ == "__main__":
    main()
