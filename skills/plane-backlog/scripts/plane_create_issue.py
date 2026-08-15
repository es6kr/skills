#!/usr/bin/env python3
"""
plane_create_issue.py — Create Plane Issues / Intake Issues via REST API or K3s Pod Fallback

Supports:
  - Markdown nested bullet tree parsing into TipTap ProseMirror JSON (nested bulletList & listItem)
  - Rich HTML structure (<ul><li><ul><li>...</li></ul></li></ul>)
  - Plain text description_stripped for search indexing
  - Idempotency guard (prevents duplicate issue creation)

Usage:
  python3 plane_create_issue.py --title "Issue title" [--description "Description text"] [--project "project_id"] [--no-intake] [--json]
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

try:
    from workspace_profile import get_profile_for_cwd
except ImportError:
    def get_profile_for_cwd(cwd=None):
        return {}


def parse_inline_tiptap(text: str) -> list:
    if not text:
        return []
    pattern = re.compile(r'(\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`)')
    nodes = []
    last_idx = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        if start > last_idx:
            nodes.append({"type": "text", "text": text[last_idx:start]})
        full_match = match.group(0)
        if full_match.startswith('['):
            link_text = match.group(2)
            link_url = match.group(3)
            nodes.append({
                "type": "text",
                "text": link_text,
                "marks": [{"type": "link", "attrs": {"href": link_url, "target": "_blank"}}]
            })
        elif full_match.startswith('**'):
            bold_text = match.group(4)
            nodes.append({
                "type": "text",
                "text": bold_text,
                "marks": [{"type": "bold"}]
            })
        elif full_match.startswith('`'):
            code_text = match.group(5)
            nodes.append({
                "type": "text",
                "text": code_text,
                "marks": [{"type": "code"}]
            })
        last_idx = end
    if last_idx < len(text):
        nodes.append({"type": "text", "text": text[last_idx:]})
    return nodes or [{"type": "text", "text": text}]


def inline_to_html(text: str) -> str:
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    return text


def parse_bullet_tokens(tokens):
    if not tokens:
        return None, ""
    min_indent = min(t[1] for t in tokens)
    items = []
    for tok_type, indent, text in tokens:
        if indent == min_indent or not items:
            items.append((text, []))
        else:
            items[-1][1].append((tok_type, indent, text))
            
    list_content = []
    html_items = []
    for item_text, sub_tokens in items:
        inline_nodes = parse_inline_tiptap(item_text)
        item_tiptap_content = [{"type": "paragraph", "content": inline_nodes}]
        html_item_str = inline_to_html(item_text)
        
        if sub_tokens:
            sub_tiptap, sub_html = parse_bullet_tokens(sub_tokens)
            if sub_tiptap:
                item_tiptap_content.append(sub_tiptap)
                html_item_str += sub_html
                
        list_content.append({
            "type": "listItem",
            "content": item_tiptap_content
        })
        html_items.append(f"<li>{html_item_str}</li>")
        
    tiptap_bullet_list = {
        "type": "bulletList",
        "content": list_content
    }
    html_bullet_list = f"<ul>{''.join(html_items)}</ul>"
    return tiptap_bullet_list, html_bullet_list


def markdown_to_tiptap_and_html(md_text: str):
    if not md_text:
        return {"type": "doc", "content": []}, "", ""
    lines = md_text.splitlines()
    tokens = []
    for line in lines:
        if not line.strip():
            tokens.append(('empty', 0, ''))
            continue
        l_stripped = line.lstrip()
        indent = len(line) - len(l_stripped)
        is_bullet = False
        item_text = ""
        if l_stripped.startswith("- [x] ") or l_stripped.startswith("- [ ] "):
            is_bullet = True
            item_text = l_stripped[6:].strip()
        elif l_stripped.startswith("- ") or l_stripped.startswith("* "):
            is_bullet = True
            item_text = l_stripped[2:].strip()
            
        if is_bullet:
            tokens.append(('bullet', indent, item_text))
            continue
            
        if l_stripped.startswith('#'):
            level = len(l_stripped) - len(l_stripped.lstrip('#'))
            heading_text = l_stripped.lstrip('#').strip()
            if 1 <= level <= 6:
                tokens.append(('heading', level, heading_text))
                continue
                
        tokens.append(('paragraph', indent, l_stripped))

    tiptap_content = []
    html_parts = []
    i = 0
    while i < len(tokens):
        tok_type, indent, text = tokens[i]
        if tok_type == 'empty':
            i += 1
            continue
        elif tok_type == 'heading':
            inline_nodes = parse_inline_tiptap(text)
            tiptap_content.append({"type": "heading", "attrs": {"level": indent}, "content": inline_nodes})
            html_parts.append(f"<h{indent}>{inline_to_html(text)}</h{indent}>")
            i += 1
        elif tok_type == 'paragraph':
            inline_nodes = parse_inline_tiptap(text)
            tiptap_content.append({"type": "paragraph", "content": inline_nodes})
            html_parts.append(f'<p class="editor-paragraph-block">{inline_to_html(text)}</p>')
            i += 1
        elif tok_type == 'bullet':
            bullet_tokens = []
            while i < len(tokens) and tokens[i][0] == 'bullet':
                bullet_tokens.append(tokens[i])
                i += 1
            node_tiptap, node_html = parse_bullet_tokens(bullet_tokens)
            if node_tiptap:
                tiptap_content.append(node_tiptap)
                html_parts.append(node_html)

    tiptap_doc = {"type": "doc", "content": tiptap_content}
    html_out = "".join(html_parts)
    return tiptap_doc, html_out, md_text


def create_via_rest_api(profile: dict, title: str, description: str = "", project_id: str = None, is_intake: bool = True) -> dict:
    plane_host = profile.get("plane_host", "").rstrip("/")
    token_env = profile.get("plane_token_env", "PLANE_API_KEY")
    token = profile.get("plane_token") or os.environ.get(token_env) or os.environ.get("PLANE_API_KEY") or os.environ.get("DGS_PLANE_API_KEY")
    workspace_slug = profile.get("workspace_name", "es6kr")
    prj_id = project_id or profile.get("default_project")

    if not plane_host or not token or not prj_id:
        return {"success": False, "reason": "Missing plane_host, plane_token, or project_id"}

    url = f"{plane_host}/api/v1/workspaces/{workspace_slug}/projects/{prj_id}/issues/"
    headers = {
        "x-api-key": token,
        "Content-Type": "application/json"
    }
    
    tiptap_doc, html_desc, plain_desc = markdown_to_tiptap_and_html(description)
    payload = {
        "name": title,
        "description": tiptap_doc,
        "description_html": html_desc,
        "description_stripped": plain_desc
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            issue_id = data.get("id")
            seq_id = data.get("sequence_id")
            issue_url = f"{plane_host}/{workspace_slug}/projects/{prj_id}/issues/{issue_id}"
            
            if is_intake:
                intake_url = f"{plane_host}/api/v1/workspaces/{workspace_slug}/projects/{prj_id}/intake-issues/"
                try:
                    intake_req = urllib.request.Request(intake_url, data=json.dumps({"issue": issue_id}).encode("utf-8"), headers=headers, method="POST")
                    urllib.request.urlopen(intake_req)
                except Exception:
                    pass

            return {
                "success": True,
                "method": "REST API",
                "id": issue_id,
                "sequence_id": seq_id,
                "title": title,
                "url": issue_url,
                "intake": is_intake
            }
    except urllib.error.HTTPError as e:
        return {"success": False, "reason": f"HTTP Error {e.code}: {e.reason}"}
    except Exception as e:
        return {"success": False, "reason": str(e)}


def create_via_k3s_fallback(profile: dict, title: str, description: str = "", project_id: str = None, is_intake: bool = True) -> dict:
    workspace_slug = profile.get("workspace_name", "es6kr")
    prj_id = project_id or profile.get("default_project") or "4b4d8bfc-5e5d-495b-bd4c-301fe89e5bb0"
    plane_host = profile.get("plane_host", "https://plane.es6.kr").rstrip("/")

    py_script = f"""import json, re
from plane.db.models import Issue, IntakeIssue, Workspace, Project, User

ws = Workspace.objects.filter(slug='{workspace_slug}').first()
prj = Project.objects.filter(id='{prj_id}').first() or Project.objects.first()
u = User.objects.filter(is_superuser=True).first() or User.objects.first()

# Idempotency check: look for existing issue with exact same title in project
existing = Issue.objects.filter(project=prj, name={json.dumps(title)}).first()
if existing:
    res = {{
        "success": True,
        "method": "Existing (Idempotency Guard)",
        "id": str(existing.id),
        "sequence_id": existing.sequence_id,
        "title": existing.name,
        "url": f"{plane_host}/{workspace_slug}/projects/{{prj.id}}/issues/{{existing.id}}",
        "intake": {str(is_intake)}
    }}
    print("RESULT_JSON:" + json.dumps(res))
    exit(0)

def parse_inline_tiptap(text: str) -> list:
    if not text:
        return []
    pattern = re.compile(r'(\\[([^\\]]+)\\]\\(([^)]+)\\)|\\*\\*([^*]+)\\*\\*|`([^`]+)`)')
    nodes = []
    last_idx = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        if start > last_idx:
            nodes.append({{"type": "text", "text": text[last_idx:start]}})
        full_match = match.group(0)
        if full_match.startswith('['):
            link_text = match.group(2)
            link_url = match.group(3)
            nodes.append({{
                "type": "text",
                "text": link_text,
                "marks": [{{"type": "link", "attrs": {{"href": link_url, "target": "_blank"}}}}]
            }})
        elif full_match.startswith('**'):
            bold_text = match.group(4)
            nodes.append({{
                "type": "text",
                "text": bold_text,
                "marks": [{{"type": "bold"}}]
            }})
        elif full_match.startswith('`'):
            code_text = match.group(5)
            nodes.append({{
                "type": "text",
                "text": code_text,
                "marks": [{{"type": "code"}}]
            }})
        last_idx = end
    if last_idx < len(text):
        nodes.append({{"type": "text", "text": text[last_idx:]}})
    return nodes or [{{"type": "text", "text": text}}]

def inline_to_html(text: str) -> str:
    text = re.sub(r'\\[([^\\]]+)\\]\\(([^)]+)\\)', r'<a href="\\2" target="_blank" rel="noopener noreferrer">\\1</a>', text)
    text = re.sub(r'\\*\\*([^*]+)\\*\\*', r'<strong>\\1</strong>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\\1</code>', text)
    return text

def parse_bullet_tokens(tokens):
    if not tokens:
        return None, ""
    min_indent = min(t[1] for t in tokens)
    items = []
    for tok_type, indent, text in tokens:
        if indent == min_indent or not items:
            items.append((text, []))
        else:
            items[-1][1].append((tok_type, indent, text))
            
    list_content = []
    html_items = []
    for item_text, sub_tokens in items:
        inline_nodes = parse_inline_tiptap(item_text)
        item_tiptap_content = [{"type": "paragraph", "content": inline_nodes}]
        html_item_str = inline_to_html(item_text)
        
        if sub_tokens:
            sub_tiptap, sub_html = parse_bullet_tokens(sub_tokens)
            if sub_tiptap:
                item_tiptap_content.append(sub_tiptap)
                html_item_str += sub_html
                
        list_content.append({
            "type": "listItem",
            "content": item_tiptap_content
        })
        html_items.append(f"<li>{html_item_str}</li>")
        
    tiptap_bullet_list = {
        "type": "bulletList",
        "content": list_content
    }
    html_bullet_list = f"<ul>{''.join(html_items)}</ul>"
    return tiptap_bullet_list, html_bullet_list

def markdown_to_tiptap_and_html(md_text: str):
    if not md_text:
        return {{"type": "doc", "content": []}}, "", ""
    lines = md_text.splitlines()
    tokens = []
    for line in lines:
        if not line.strip():
            tokens.append(('empty', 0, ''))
            continue
        l_stripped = line.lstrip()
        indent = len(line) - len(l_stripped)
        is_bullet = False
        item_text = ""
        if l_stripped.startswith("- [x] ") or l_stripped.startswith("- [ ] "):
            is_bullet = True
            item_text = l_stripped[6:].strip()
        elif l_stripped.startswith("- ") or l_stripped.startswith("* "):
            is_bullet = True
            item_text = l_stripped[2:].strip()
            
        if is_bullet:
            tokens.append(('bullet', indent, item_text))
            continue
            
        if l_stripped.startswith('#'):
            level = len(l_stripped) - len(l_stripped.lstrip('#'))
            heading_text = l_stripped.lstrip('#').strip()
            if 1 <= level <= 6:
                tokens.append(('heading', level, heading_text))
                continue
                
        tokens.append(('paragraph', indent, l_stripped))

    tiptap_content = []
    html_parts = []
    i = 0
    while i < len(tokens):
        tok_type, indent, text = tokens[i]
        if tok_type == 'empty':
            i += 1
            continue
        elif tok_type == 'heading':
            inline_nodes = parse_inline_tiptap(text)
            tiptap_content.append({{"type": "heading", "attrs": {{"level": indent}}, "content": inline_nodes}})
            html_parts.append(f"<h{{indent}}>{{inline_to_html(text)}}</h{{level}}>")
            i += 1
        elif tok_type == 'paragraph':
            inline_nodes = parse_inline_tiptap(text)
            tiptap_content.append({{"type": "paragraph", "content": inline_nodes}})
            html_parts.append(f'<p class="editor-paragraph-block">{{inline_to_html(text)}}</p>')
            i += 1
        elif tok_type == 'bullet':
            bullet_tokens = []
            while i < len(tokens) and tokens[i][0] == 'bullet':
                bullet_tokens.append(tokens[i])
                i += 1
            node_tiptap, node_html = parse_bullet_tokens(bullet_tokens)
            if node_tiptap:
                tiptap_content.append(node_tiptap)
                html_parts.append(node_html)

    tiptap_doc = {{"type": "doc", "content": tiptap_content}}
    html_out = "".join(html_parts)
    return tiptap_doc, html_out, md_text

desc_text = {json.dumps(description)}
tiptap_doc, html_desc, plain_desc = markdown_to_tiptap_and_html(desc_text)

issue = Issue.objects.create(
    name={json.dumps(title)},
    description=tiptap_doc,
    description_html=html_desc,
    description_stripped=plain_desc,
    project=prj,
    workspace=ws,
    created_by=u
)

if {str(is_intake)}:
    try:
        IntakeIssue.objects.create(issue=issue, project=prj, workspace=ws, created_by=u, status=0)
    except Exception:
        pass

res = {{
    "success": True,
    "method": "K3s Django Shell Fallback",
    "id": str(issue.id),
    "sequence_id": issue.sequence_id,
    "title": issue.name,
    "url": f"{plane_host}/{workspace_slug}/projects/{{prj.id}}/issues/{{issue.id}}",
    "intake": {str(is_intake)}
}}
print("RESULT_JSON:" + json.dumps(res))
"""

    b64_script = base64.b64encode(py_script.encode('utf-8')).decode('utf-8')
    cmd = [
        "kubectl", "exec", "-n", "plane", "deploy/plane-api-wl", "--",
        "python3", "manage.py", "shell", "-c",
        f"import base64; exec(base64.b64decode('{b64_script}').decode('utf-8'))"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        for line in res.stdout.splitlines():
            if line.startswith("RESULT_JSON:"):
                return json.loads(line[len("RESULT_JSON:"):])
        return {"success": False, "reason": f"No RESULT_JSON line output. Stdout: {res.stdout}, Stderr: {res.stderr}"}
    except subprocess.CalledProcessError as e:
        return {"success": False, "reason": f"K3s execution failed: {e.stderr or e.stdout or str(e)}"}
    except Exception as e:
        return {"success": False, "reason": f"K3s execution failed: {str(e)}"}


def create_plane_issue(title: str, description: str = "", project_id: str = None, is_intake: bool = True, cwd: str = None) -> dict:
    profile = get_profile_for_cwd(cwd or os.getcwd())
    res = create_via_rest_api(profile, title, description, project_id, is_intake)
    if res.get("success"):
        return res
    
    # Fallback to K3s django shell
    res_k3s = create_via_k3s_fallback(profile, title, description, project_id, is_intake)
    if res_k3s.get("success"):
        return res_k3s
    
    return {"success": False, "reason": f"Both API ({res.get('reason')}) and K3s fallback ({res_k3s.get('reason')}) failed"}


def main():
    parser = argparse.ArgumentParser(description="Create Plane Issue / Intake Issue")
    parser.add_argument("--title", required=True, help="Issue title")
    parser.add_argument("--description", default="", help="Issue description")
    parser.add_argument("--project", default=None, help="Project ID or slug")
    parser.add_argument("--no-intake", action="store_true", help="Do not mark as intake issue")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()
    res = create_plane_issue(args.title, args.description, args.project, is_intake=not args.no_intake)

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if res.get("success"):
            print(f"✅ Created Plane Issue [{res.get('sequence_id')}] via {res.get('method')}")
            print(f"   Title: {res.get('title')}")
            print(f"   URL:   {res.get('url')}")
        else:
            print(f"❌ Failed to create issue: {res.get('reason')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
