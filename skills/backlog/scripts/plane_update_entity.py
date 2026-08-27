#!/usr/bin/env python3
"""
plane_update_entity.py — Update existing Plane Issues / Pages via REST API or K3s Fallback

Supports:
  - Updating Issue title, priority, and rich markdown description via REST API / K3s
  - Updating Page title and rich markdown description via K3s / REST API
  - Reading description from markdown file (--description-file) or string (--description)
  - Resolving issue by UUID or sequence key (e.g., AIAUTO-92, 92)
  - 1:1 Priority normalization (P0-P3 <-> urgent/high/medium/low/none)

Usage:
  python3 plane_update_entity.py --issue AIAUTO-92 --description-file path/to/doc.md
  python3 plane_update_entity.py --issue-id <uuid> --priority P1 --description "New body"
  python3 plane_update_entity.py --type page --page-id <uuid> --description-file doc.md
"""

import sys
import os
import argparse
import json
import urllib.request
import urllib.error
import subprocess
import base64
import re
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (plane-backlog)"


def _shared_script_dirs():
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    candidates = [SCRIPT_DIR]
    for skill in ("plane-backlog", "fix-plan"):
        if plugin_root:
            candidates.append(os.path.join(plugin_root, "skills", skill, "scripts"))
        candidates.append(
            os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir, os.pardir, skill, "scripts"))
        )
    return [d for d in candidates if d and os.path.isdir(d)]


for _shared_dir in _shared_script_dirs():
    if _shared_dir not in sys.path:
        sys.path.insert(0, _shared_dir)

from plane_client import resolve_profile, normalize_priority, convert_document  # noqa: E402
from plane_create_entity import markdown_to_tiptap_and_html  # noqa: E402


def build_k3s_update_script(
    workspace_slug: str,
    prj_id: str,
    plane_host: str,
    entity_type: str,
    entity_id: str,
    title: str = None,
    description: str = None,
    normalized_priority: str = None,
) -> str:
    """Build the Django-shell script to update Issue or Page in Plane DB."""
    tiptap_doc, html_desc, plain_desc = (
        markdown_to_tiptap_and_html(description)
        if description is not None
        else (None, None, None)
    )

    # A Page also keeps a Yjs CRDT copy (description_binary) that the editor
    # treats as authoritative. Writing the HTML/JSON/text fields without it
    # leaves the representations disagreeing, which surfaces to the user as
    # "the page still shows the old content". Derive both from the same HTML
    # via Plane's own converter so they cannot diverge. Issues do not use the
    # CRDT path (their description_binary stays empty), so this is page-only.
    binary_b64 = None
    if entity_type == "page" and html_desc is not None:
        canonical_tiptap, binary_b64 = convert_document(plane_host, html_desc)
        if canonical_tiptap is not None:
            tiptap_doc = canonical_tiptap

    return f"""import base64, json, re
from plane.db.models import Issue, Page, Workspace, Project

ws = Workspace.objects.filter(slug__iexact={repr(workspace_slug)}).first()
prj_raw = {repr(prj_id)}
prj = None
if prj_raw:
    if re.match(r'^[0-9a-fA-F-]{{36}}$', prj_raw):
        prj = Project.objects.filter(id=prj_raw).first()
    else:
        if ws:
            prj = Project.objects.filter(workspace=ws, identifier__iexact=prj_raw).first() or Project.objects.filter(workspace=ws, name__iexact=prj_raw).first()
        if not prj:
            prj = Project.objects.filter(identifier__iexact=prj_raw).first() or Project.objects.filter(name__iexact=prj_raw).first()

entity_type = {repr(entity_type)}
target_id = {repr(entity_id)}
new_title = {repr(title)}
new_html = {repr(html_desc)}
new_plain = {repr(plain_desc)}
new_priority = {repr(normalized_priority)}
new_tiptap = {repr(tiptap_doc)}
new_binary_b64 = {repr(binary_b64)}

res = {{"success": False}}

if entity_type == "page":
    # Lookup by ID
    page = Page.objects.filter(id=target_id).first() if target_id else None
    if not page and new_title and prj:
        page = Page.objects.filter(projects=prj, name=new_title).first()
    if not page and new_title and ws:
        page = Page.objects.filter(workspace=ws, name=new_title).first()
    
    if page:
        if new_title:
            page.name = new_title
        if new_html is not None:
            page.description_html = new_html
            page.description_stripped = new_plain
        if new_tiptap is not None:
            page.description = new_tiptap
        if new_binary_b64:
            page.description_binary = base64.b64decode(new_binary_b64)
        page.save()
        res = {{
            "success": True,
            "method": "K3s Django Shell Fallback",
            "type": "page",
            "id": str(page.id),
            "name": page.name,
            "description_html_len": len(page.description_html or ""),
            "description_binary_len": len(bytes(page.description_binary or b"")),
            "binary_written": bool(new_binary_b64)
        }}
    else:
        res = {{"success": False, "reason": f"Page {{target_id}} not found in DB"}}

else:
    # Issue lookup by UUID or sequence_id
    issue = None
    if target_id:
        if re.match(r'^[0-9a-fA-F-]{{36}}$', target_id):
            issue = Issue.objects.filter(id=target_id).first()
        else:
            m = re.search(r'(\\d+)$', target_id)
            if m:
                seq = int(m.group(1))
                if prj:
                    issue = Issue.objects.filter(project=prj, sequence_id=seq).first()
                if not issue and ws:
                    issue = Issue.objects.filter(workspace=ws, sequence_id=seq).first()
                if not issue:
                    issue = Issue.objects.filter(sequence_id=seq).first()

    if not issue and new_title and prj:
        issue = Issue.objects.filter(project=prj, name=new_title).first()

    if issue:
        if new_title:
            issue.name = new_title
        if new_html is not None:
            issue.description_html = new_html
            issue.description_stripped = new_plain
        if new_tiptap is not None:
            issue.description = new_tiptap
        if new_priority:
            issue.priority = new_priority
        issue.save()
        res = {{
            "success": True,
            "method": "K3s Django Shell Fallback",
            "type": "issue",
            "id": str(issue.id),
            "sequence_id": issue.sequence_id,
            "name": issue.name,
            "priority": issue.priority,
            "description_html_len": len(issue.description_html or "")
        }}
    else:
        res = {{"success": False, "reason": f"Issue {{target_id}} not found in DB"}}

print("RESULT_JSON:" + json.dumps(res))
"""


def update_via_k3s_fallback(
    profile: dict,
    entity_type: str,
    entity_id: str,
    title: str = None,
    description: str = None,
    priority: str = None,
    project_id: str = None,
) -> dict:
    normalized_priority = normalize_priority(priority) if priority else None
    workspace_slug = profile.get("workspace_slug")
    prj_id = project_id or profile.get("default_project")
    plane_host = (profile.get("plane_host") or "").rstrip("/")

    kubectl = shutil.which("kubectl")
    if not kubectl:
        return {"success": False, "reason": "kubectl not found on PATH for K3s fallback"}

    k3s_namespace = (
        profile.get("k3s_namespace") or os.environ.get("PLANE_K3S_NAMESPACE") or "plane"
    )
    k3s_workload = (
        profile.get("k3s_workload")
        or os.environ.get("PLANE_K3S_WORKLOAD")
        or "deploy/plane-api-wl"
    )
    k3s_kubeconfig = profile.get("k3s_kubeconfig") or os.environ.get("PLANE_K3S_KUBECONFIG")

    py_script = build_k3s_update_script(
        workspace_slug,
        prj_id,
        plane_host,
        entity_type,
        entity_id,
        title,
        description,
        normalized_priority,
    )
    b64_script = base64.b64encode(py_script.encode("utf-8")).decode("utf-8")
    k3s_ssh_host = profile.get("k3s_ssh_host")
    if k3s_ssh_host:
        cmd = [
            "ssh",
            k3s_ssh_host,
            f"kubectl exec -n {k3s_namespace} {k3s_workload} -- python3 manage.py shell -c \"import base64; exec(base64.b64decode('{b64_script}').decode('utf-8'))\"",
        ]
    else:
        cmd = [kubectl]
        if k3s_kubeconfig:
            cmd.extend(["--kubeconfig", k3s_kubeconfig])
        cmd.extend(
            [
                "exec",
                "-n",
                k3s_namespace,
                k3s_workload,
                "--",
                "python3",
                "manage.py",
                "shell",
                "-c",
                f"import base64; exec(base64.b64decode('{b64_script}').decode('utf-8'))",
            ]
        )

    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        for line in proc.stdout.splitlines():
            if line.startswith("RESULT_JSON:"):
                return json.loads(line[len("RESULT_JSON:"):])
        return {
            "success": False,
            "reason": f"No RESULT_JSON line emitted. Output: {proc.stdout.strip()}",
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "reason": f"K3s kubectl exec failed: {e.stderr.strip() or e.stdout.strip()}",
        }
    except Exception as e:
        return {"success": False, "reason": str(e)}


def update_via_rest_api(
    profile: dict,
    entity_type: str,
    entity_id: str,
    title: str = None,
    description: str = None,
    priority: str = None,
    project_id: str = None,
) -> dict:
    plane_host = (profile.get("plane_host") or "").rstrip("/")
    token = profile.get("token")
    workspace_slug = profile.get("workspace_slug")
    prj_id = project_id or profile.get("default_project")

    if not plane_host or not token or not workspace_slug or not prj_id or not entity_id:
        return {"success": False, "reason": "Missing required fields for REST API update"}

    # Resolve sequence key (e.g. AIAUTO-92 or 92) to issue UUID if needed
    issue_uuid = entity_id
    if entity_type == "issue" and not re.match(r"^[0-9a-fA-F-]{36}$", entity_id):
        m = re.search(r"(\d+)$", entity_id)
        if m:
            seq_num = int(m.group(1))
            list_url = f"{plane_host}/api/v1/workspaces/{workspace_slug}/projects/{prj_id}/issues/?sequence_id={seq_num}"
            headers = {"x-api-key": token, "User-Agent": UA}
            try:
                req = urllib.request.Request(list_url, headers=headers)
                with urllib.request.urlopen(req) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    results = data.get("results") if isinstance(data, dict) else data
                    if results:
                        for itm in results:
                            if itm.get("sequence_id") == seq_num:
                                issue_uuid = itm.get("id")
                                break
            except Exception:
                pass

    if entity_type == "page":
        url = f"{plane_host}/api/v1/workspaces/{workspace_slug}/projects/{prj_id}/pages/{issue_uuid}/"
    else:
        url = f"{plane_host}/api/v1/workspaces/{workspace_slug}/projects/{prj_id}/issues/{issue_uuid}/"

    headers = {
        "x-api-key": token,
        "Content-Type": "application/json",
        "User-Agent": UA,
    }

    payload = {}
    if title:
        payload["name"] = title
    if description is not None:
        tiptap_doc, html_desc, plain_desc = markdown_to_tiptap_and_html(description)
        payload["description_html"] = html_desc
        payload["description_stripped"] = plain_desc
    if priority and entity_type == "issue":
        payload["priority"] = normalize_priority(priority)

    if not payload:
        return {"success": False, "reason": "No update fields provided"}

    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="PATCH"
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "success": True,
                "method": "Plane REST API",
                "id": data.get("id"),
                "sequence_id": data.get("sequence_id"),
                "name": data.get("name"),
                "priority": data.get("priority"),
                "url": f"{plane_host}/{workspace_slug}/projects/{prj_id}/{'pages' if entity_type == 'page' else 'issues'}/{data.get('id')}",
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return {"success": False, "reason": f"REST API HTTP {e.code}: {err_body}"}
    except Exception as e:
        return {"success": False, "reason": str(e)}


def update_entity(
    profile: dict,
    entity_type: str,
    entity_id: str,
    title: str = None,
    description: str = None,
    priority: str = None,
    project_id: str = None,
) -> dict:
    # 1. Attempt REST API update
    res = update_via_rest_api(
        profile, entity_type, entity_id, title, description, priority, project_id
    )
    if res.get("success"):
        return res

    # 2. Fallback to K3s DB update
    res_k3s = update_via_k3s_fallback(
        profile, entity_type, entity_id, title, description, priority, project_id
    )
    if res_k3s.get("success"):
        return res_k3s

    return {
        "success": False,
        "reason": f"REST API failed ({res.get('reason')}) and K3s fallback failed ({res_k3s.get('reason')})",
    }


def main():
    parser = argparse.ArgumentParser(description="Update existing Plane Issue or Page")
    parser.add_argument(
        "--type", choices=["issue", "page"], default="issue", help="Entity type (default: issue)"
    )
    parser.add_argument("--id", help="Target Issue or Page UUID")
    parser.add_argument(
        "--issue", "--issue-id", dest="issue_id", help="Target Issue key (e.g. AIAUTO-92) or UUID"
    )
    parser.add_argument("--page", "--page-id", dest="page_id", help="Target Page UUID")
    parser.add_argument("--title", "--name", dest="title", help="New title/name")
    parser.add_argument("--description", help="New description markdown")
    parser.add_argument(
        "--description-file", help="Path to markdown file containing new description"
    )
    parser.add_argument("-p", "--priority", help="P0-P3 or urgent/high/medium/low/none")
    parser.add_argument("--project", help="Project ID or slug override")
    parser.add_argument(
        "--workspace", help="Workspace name, slug, or directory path override"
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    # Determine entity type and target ID
    entity_type = args.type
    entity_id = args.id
    if args.issue_id:
        entity_id = args.issue_id
        entity_type = "issue"
    elif args.page_id:
        entity_id = args.page_id
        entity_type = "page"

    if not entity_id and not args.title:
        sys.stderr.write("Error: Must provide target entity via --id, --issue, or --page\n")
        sys.exit(1)

    description = args.description
    if args.description_file:
        if not os.path.exists(args.description_file):
            sys.stderr.write(f"Error: description file not found: {args.description_file}\n")
            sys.exit(1)
        with open(args.description_file, "r", encoding="utf-8") as f:
            description = f.read()

    profile = resolve_profile(args.workspace or args.project)
    res = update_entity(
        profile, entity_type, entity_id, args.title, description, args.priority, args.project
    )

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if res.get("success"):
            print(
                f"Successfully updated {entity_type} {res.get('sequence_id') or res.get('id')}: {res.get('name')}"
            )
            if res.get("url"):
                print(f"URL: {res.get('url')}")
            print(f"Method: {res.get('method')}")
        else:
            sys.stderr.write(f"Failed to update {entity_type}: {res.get('reason')}\n")
            sys.exit(1)


if __name__ == "__main__":
    main()
