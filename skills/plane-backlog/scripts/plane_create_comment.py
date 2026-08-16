#!/usr/bin/env python3
"""
plane_create_comment.py — Post a comment onto a Plane Issue via REST API.

Companion to plane_create_issue.py. Used by the canonicalization flow to attach a
parent issue's nested sub-findings (or any follow-up note) as issue comments, instead
of creating separate sub-issues.

Key correctness points (learned the hard way):
  - Plane validates `comment_html` (bleach/lxml). Raw markdown text containing `<`, `>`,
    `&` produces HTTP 400 "Invalid HTML passed". This script HTML-escapes the text first,
    then re-applies only safe inline formatting (link / bold / code) on the escaped text.
  - plane.es6.kr sits behind Cloudflare, which 403s the default `Python-urllib` User-Agent.
    A browser-like User-Agent header is required.
  - The workspace profile's `default_project` is often an identifier ("es6kr"), NOT the
    project UUID the REST path needs. This script resolves the UUID from /projects/.
  - Bulk posting hits Plane's rate limiter (HTTP 429). Requests retry with backoff.

Usage:
  python3 plane_create_comment.py --issue <issue_uuid> --comment "text with **bold** [link](url)" [--project <uuid>] [--json]
  python3 plane_create_comment.py --issue <issue_uuid> --comment-file path/to/comment.md [--json]
"""
import sys, os, json, time, html, re, argparse
import urllib.request, urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _shared_script_dirs():
    """Directories holding the shared plane-backlog / fix-plan script modules.

    Resolved relative to this file and ``CLAUDE_PLUGIN_ROOT`` so the lookup does
    not depend on any particular install layout under the user's home.
    """
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

# Single source of truth for profile resolution — see plane_client.resolve_profile.
from plane_client import resolve_profile  # noqa: E402

UA = "Mozilla/5.0 (plane-backlog)"


def _request(method, url, token, payload=None, retries=5):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"x-api-key": token, "Content-Type": "application/json", "User-Agent": UA}
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 502, 503) and attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            raise
    if last:
        raise last


def markdown_to_safe_html(md: str) -> str:
    """Escape first (valid HTML guarantee), then re-apply safe inline link/bold/code."""
    def inline(t: str) -> str:
        t = html.escape(t)
        t = re.sub(r'\[([^\]]+)\]\((https?://[^)\s]+)\)',
                   r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', t)
        t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
        t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
        return t
    parts, ul_open = [], False
    for line in md.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("- ") or s.startswith("* "):
            if not ul_open:
                parts.append("<ul>"); ul_open = True
            parts.append(f"<li>{inline(s[2:])}</li>")
        else:
            if ul_open:
                parts.append("</ul>"); ul_open = False
            parts.append(f"<p>{inline(s)}</p>")
    if ul_open:
        parts.append("</ul>")
    return "".join(parts) or "<p></p>"


def resolve_project(host, ws, token, want):
    """Resolve a project UUID. `want` may already be a UUID or an identifier/name."""
    if want and re.fullmatch(r"[0-9a-fA-F-]{36}", want):
        return want
    d = _request("GET", f"{host}/api/v1/workspaces/{ws}/projects/", token)
    results = d.get("results", d if isinstance(d, list) else [])
    for p in results:
        if want and (p.get("identifier", "").lower() == want.lower()
                     or p.get("name", "").lower() == want.lower()):
            return p.get("id")
    # single-project workspace fallback
    if len(results) == 1:
        return results[0].get("id")
    return None


def create_comment(issue_id, comment_md, project=None, cwd=None):
    profile = resolve_profile(cwd or os.getcwd())
    host = (profile.get("plane_host") or "").rstrip("/")
    ws = profile.get("workspace_slug")
    token = profile.get("token")
    missing = [
        name
        for name, value in (("plane_host", host), ("token", token), ("workspace_slug", ws))
        if not value
    ]
    if missing:
        return {
            "success": False,
            "reason": (
                f"Unresolved workspace profile fields: {', '.join(missing)}. "
                "Refusing to guess a target workspace."
            ),
        }
    prj = resolve_project(host, ws, token, project or profile.get("default_project"))
    if not prj:
        return {"success": False, "reason": "Could not resolve project UUID — pass --project <uuid>"}
    url = f"{host}/api/v1/workspaces/{ws}/projects/{prj}/issues/{issue_id}/comments/"
    try:
        d = _request("POST", url, token, {"comment_html": markdown_to_safe_html(comment_md)})
        return {"success": True, "id": d.get("id"), "issue": issue_id, "project": prj,
                "url": f"{host}/{ws}/projects/{prj}/issues/{issue_id}"}
    except urllib.error.HTTPError as e:
        return {"success": False, "reason": f"HTTP {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"success": False, "reason": str(e)}


def main():
    ap = argparse.ArgumentParser(description="Post a comment onto a Plane issue")
    ap.add_argument("--issue", required=True, help="Issue UUID")
    ap.add_argument("--comment", default=None, help="Comment text (markdown inline: **bold** `code` [t](url))")
    ap.add_argument("--comment-file", default=None, help="Read comment markdown from a file")
    ap.add_argument("--project", default=None, help="Project UUID or identifier (default: workspace profile)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    md = a.comment
    if a.comment_file:
        with open(a.comment_file, encoding="utf-8") as f:
            md = f.read()
    if not md:
        print("error: provide --comment or --comment-file", file=sys.stderr); sys.exit(2)
    res = create_comment(a.issue, md, a.project)
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif res.get("success"):
        print(f"✅ Comment posted on issue {a.issue}\n   {res['url']}")
    else:
        print(f"❌ Failed: {res.get('reason')}"); sys.exit(1)


if __name__ == "__main__":
    main()
