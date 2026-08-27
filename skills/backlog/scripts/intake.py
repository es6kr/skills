#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plane Intake Batch Registration Script
Registers untracked fix_plan.md backlog items with high project-classification confidence as Plane Intake issues.
"""

import os
import sys
import re
import json
import time
import argparse
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FIX_PLAN = r"C:\Users\DAEGUNSOFT\ghq\github.com\daegunsoftDev\.agents\fix_plan.md"
BASE_URL = "https://plane.dgs.ai.kr/api/v1/workspaces/dgs"
UA = "Mozilla/5.0 (plane)"

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

def classify_project_with_confidence(text, section):
    """
    Returns (project, confidence, matched_keywords)
    confidence: 'high' (clear domain keywords) vs 'low' (ambiguous/general)
    """
    clean_text = re.sub(r'^\s*-\s*\[(?: |/|BLOCKED).*?\]\s*', '', text).strip()
    title_match = re.match(r'^([^(\n\r*—]+)', clean_text)
    title_part = title_match.group(1).lower() if title_match else clean_text[:60].lower()
    full_lower = text.lower()
    
    # 1. INFRA
    infra_kw = ["k3s", "k8s", "nginx", "tls", "cert", "vault", "iac", "terraform", "ansible", "server", "ssh", "netnat", "portainer", "dns", "tailscale", "ip", "timescaledb", "hypertable", "postgres", "통합서버", "운영서버", "gitops", "argocd", "secret", "배포환경"]
    infra_matches = [k for k in infra_kw if k in full_lower]
    infra_title_matches = [k for k in infra_kw if k in title_part]
    
    # 2. AIAUTO
    ai_kw = ["clawe", "clawo", "rag", "qdrant", "hook", "fable agent", "docent", "skill", "agent", "prompt", "llm", "fix-plan", "cleanup", "fa-classify", "failed-attempts", "ralph-loop", "ai 활용", "에이전트"]
    ai_matches = [k for k in ai_kw if k in full_lower]
    ai_title_matches = [k for k in ai_kw if k in title_part]
    
    # 3. DTWEB
    web_kw = ["dt", "turborepo", "nextjs", "prisma", "brand", "sso", "authentik", "logout", "frontend", "zap", "csp", "pmtiles", "discord", "discord 전용채널"]
    web_matches = [k for k in web_kw if k in full_lower]
    web_title_matches = [k for k in web_kw if k in title_part]
    
    # 4. OPS
    ops_kw = ["교육", "회의", "coc", "일하는 방식", "핵심 가치", "discovery", "대외 확정"]
    ops_matches = [k for k in ops_kw if k in full_lower]
    ops_title_matches = [k for k in ops_kw if k in title_part]
    
    # Score with 3x multiplier for title matches
    scores = {
        "INFRA": len(infra_matches) + 3 * len(infra_title_matches),
        "AIAUTO": len(ai_matches) + 3 * len(ai_title_matches),
        "DTWEB": len(web_matches) + 3 * len(web_title_matches),
        "OPS": len(ops_matches) + 3 * len(ops_title_matches)
    }
    
    best_proj = max(scores, key=scores.get)
    best_score = scores[best_proj]
    
    if best_score >= 1:
        other_scores = [s for p, s in scores.items() if p != best_proj]
        if max(other_scores) == 0 or best_score > max(other_scores):
            all_m = infra_matches if best_proj == "INFRA" else (ai_matches if best_proj == "AIAUTO" else (web_matches if best_proj == "DTWEB" else ops_matches))
            return best_proj, "high", all_m
            
    return best_proj, "low", []

def fetch_project_map(headers):
    req = urllib.request.Request(f"{BASE_URL}/projects/", headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        projects = data.get('results', data if isinstance(data, list) else [])
    return {p['identifier']: p['id'] for p in projects}

def parse_untracked_items(fix_plan_path):
    if not os.path.exists(fix_plan_path):
        return []

    with open(fix_plan_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    untracked_list = []
    alt_issue_pattern = re.compile(r'\[([A-Z]+)-(\d+)\]')
    alt_prio_pattern = re.compile(r'\[(?:BLOCKED:)?(P[0-3])(?::[a-z]+)?\]')
    checkbox_pattern = re.compile(r'^\s*-\s*\[(?: |/|BLOCKED).*\]')

    current_section = ""
    for line_idx, line in enumerate(lines, 1):
        if line.startswith("## "):
            current_section = line.strip()
            continue

        if not checkbox_pattern.match(line):
            continue

        if alt_issue_pattern.search(line) or "plane.dgs.ai.kr" in line:
            continue

        if current_section in ("## Flow Chart", "## Pipeline Execution Log", "## Completed", "## Hold", "## REPEAT"):
            continue

        p_match = alt_prio_pattern.search(line)
        prio_raw = p_match.group(1) if p_match else "P2"
        prio = PRIORITY_MAP.get(prio_raw, "medium")

        if bool(re.search(r'\bdeff?erred\b', line, re.IGNORECASE)):
            prio = "low"
            prio_raw = "P3:deferred"

        reg_m = re.search(r'(?:index화|index 재추가|등록일?)\s*(\d{4}-\d{2}-\d{2})', line)
        start_date = reg_m.group(1) if reg_m else None

        clean_text = re.sub(r'^\s*-\s*\[(?: |/|BLOCKED).*?\]\s*', '', line).strip()
        title_match = re.match(r'^([^(\n\r*—]+)', clean_text)
        title = title_match.group(1).strip() if title_match else clean_text[:60]
        if len(title) < 5:
            title = clean_text[:60]

        proj, conf, kws = classify_project_with_confidence(line, current_section)

        untracked_list.append({
            "line_no": line_idx,
            "section": current_section,
            "priority_raw": prio_raw,
            "priority": prio,
            "title": title,
            "project": proj,
            "confidence": conf,
            "matched_keywords": kws,
            "start_date": start_date,
            "raw_line": line.strip()
        })

    return untracked_list

def create_plane_intake_issue(project_id, title, description, priority, start_date, headers):
    url = f"{BASE_URL}/projects/{project_id}/issues/"
    body = {
        "name": title,
        "description_html": f"<p>{description}</p>",
        "description": description,
        "priority": priority
    }
    if start_date:
        body["start_date"] = start_date

    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    for attempt in range(4):
        try:
            with urllib.request.urlopen(req) as resp:
                res_data = json.loads(resp.read().decode('utf-8'))
                return res_data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = 2.0 * (attempt + 1)
                time.sleep(wait_time)
            else:
                try:
                    err_msg = e.read().decode('utf-8')
                except Exception:
                    err_msg = str(e)
                print(f"    [Error] HTTP {e.code}: {err_msg}")
                return None
        except Exception as e:
            print(f"    [Error] {e}")
            return None
    return None

def main():
    parser = argparse.ArgumentParser(description="Plane Intake Batch Creation Tool")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Preview classified items without creating issues")
    parser.add_argument("--execute", action="store_true", default=False, help="Execute physical creation in Plane API")
    parser.add_argument("--high-confidence-only", action="store_true", default=True, help="Only process items with high classification confidence")
    parser.add_argument("--all-confidence", action="store_true", default=False, help="Process all items regardless of confidence")
    parser.add_argument("--project", help="Filter by specific target project (INFRA, AIAUTO, DTWEB, OPS)")
    parser.add_argument("--section", help="Filter by section (e.g. '## Priority Tasks')")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of items to register (0=unlimited)")
    parser.add_argument("--link-back", action="store_true", default=True, help="Update fix_plan.md lines with created Plane issue links")
    parser.add_argument("--fix-plan", default=DEFAULT_FIX_PLAN, help="Path to fix_plan.md")
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("Error: DGS_PLANE_API_KEY not found.")
        sys.exit(1)

    headers = {
        "X-API-Key": api_key,
        "User-Agent": UA,
        "Content-Type": "application/json"
    }

    project_map = fetch_project_map(headers)
    untracked = parse_untracked_items(args.fix_plan)

    filtered = []
    for u in untracked:
        if not args.all_confidence and u["confidence"] != "high":
            continue
        if args.project and u["project"] != args.project:
            continue
        if args.section and u["section"] != args.section:
            continue
        filtered.append(u)

    if args.limit > 0:
        filtered = filtered[:args.limit]

    print("=" * 100)
    print("PLANE INTAKE BATCH CLASSIFICATION & REGISTRATION REPORT")
    print("=" * 100)
    print(f"Total Untracked Found: {len(untracked)} | Filtered for Intake: {len(filtered)}")
    print(f"Filters: High Confidence Only={not args.all_confidence}, Project={args.project or 'ALL'}, Section={args.section or 'ALL'}")
    print("-" * 100)

    if not filtered:
        print("No items matched filter criteria.")
        return

    print("\n📋  [CLASSIFIED INTAKE CANDIDATES]:")
    for idx, f in enumerate(filtered, 1):
        kw_str = f" (matched: {', '.join(f['matched_keywords'])})" if f['matched_keywords'] else ""
        print(f"  [{idx:2d}] L{f['line_no']:<4} [{f['project']}] [{f['priority_raw']}] {f['title'][:50]:<50} | {f['section']}{kw_str}")

    if args.dry_run or not args.execute:
        print("\n" + "=" * 100)
        print("✔ Dry-run complete. To physically register these items into Plane, run with '--execute'.")
        return

    print("\n🚀  [EXECUTING INTAKE CREATION TO PLANE API]...")
    created_count = 0
    created_results = []

    # Read fix_plan for link-back
    fix_plan_lines = []
    if args.link_back and os.path.exists(args.fix_plan):
        with open(args.fix_plan, 'r', encoding='utf-8') as fp:
            fix_plan_lines = fp.readlines()

    for idx, f in enumerate(filtered, 1):
        proj_id = project_map.get(f["project"])
        if not proj_id:
            print(f"  ✖ [{idx}/{len(filtered)}] Project ID not found for {f['project']}")
            continue

        print(f"  Creating [{idx}/{len(filtered)}] [{f['project']}] {f['title'][:40]}...", end="", flush=True)
        res = create_plane_intake_issue(
            project_id=proj_id,
            title=f["title"],
            description=f["raw_line"],
            priority=f["priority"],
            start_date=f["start_date"],
            headers=headers
        )

        if res:
            seq = res.get("sequence_id")
            issue_id = res.get("id")
            key = f"{f['project']}-{seq}"
            url = f"https://plane.dgs.ai.kr/dgs/projects/{proj_id}/issues/{issue_id}"
            created_count += 1
            print(f" ✔ Created [{key}]")
            
            created_results.append({
                "key": key,
                "id": issue_id,
                "line_no": f["line_no"],
                "project": f["project"],
                "title": f["title"],
                "url": url,
                "raw_line": f["raw_line"]
            })

            # Update in-memory line
            if fix_plan_lines and f["line_no"] <= len(fix_plan_lines):
                target_idx = f["line_no"] - 1
                orig_line = fix_plan_lines[target_idx]
                if f["title"] in orig_line:
                    # Insert [KEY] after checkbox and append Plane link
                    m = re.match(r'^(\s*-\s*\[(?: |/|BLOCKED).*?\]\s*)(.*)$', orig_line)
                    if m:
                        prefix = m.group(1)
                        rest = m.group(2).rstrip()
                        new_line = f"{prefix}[{key}] {rest} → Plane ({url})\n"
                        fix_plan_lines[target_idx] = new_line
        else:
            print(" ✖ Failed")

        time.sleep(0.35)

    if args.link_back and created_results and fix_plan_lines:
        with open(args.fix_plan, 'w', encoding='utf-8') as fp:
            fp.writelines(fix_plan_lines)
        print(f"✔ Successfully linked {len(created_results)} newly created Plane issue keys back into {args.fix_plan}.")

    print("\n" + "=" * 100)
    print(f"Finished: {created_count}/{len(filtered)} Intake issues successfully created in Plane.")
    print("=" * 100)

if __name__ == "__main__":
    main()
