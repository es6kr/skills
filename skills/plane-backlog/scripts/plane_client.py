#!/usr/bin/env python3
"""plane_client.py — reusable Plane REST client for backlog scripts.

Factors out the API plumbing that fix-plan / plane-backlog scripts kept
re-implementing per session in throwaway scratch files:

  * request throttling + HTTP 429 backoff (bulk tracker reconciliation hits the
    rate limit almost immediately without it)
  * batch listing per project instead of one GET per issue
  * an on-disk issue cache so a re-run after a crash does not re-fetch
  * ``description_html`` -> text, because Plane leaves ``description_stripped``
    empty for issues created through the API, which silently breaks any
    matching that reads the stripped field

Standard library only — these scripts run under bare ``python3`` with no venv.

Usage::

    from plane_client import PlaneClient

    client = PlaneClient()                       # profile resolved from cwd
    issues = client.list_issues(project_id)      # cached + throttled
    client.patch_issue(project_id, issue_id, {"state": state_id})
"""

import html as _html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

DEFAULT_THROTTLE = 1.2
RATE_LIMIT_FIRST_WAIT = 65
RATE_LIMIT_RETRY_WAIT = 30
MAX_ATTEMPTS = 4
PAGE_SIZE = 100


def resolve_profile(cwd=None):
    """Return the workspace profile dict (plane_host / token / slug / project).

    Delegates to the sibling ``workspace_profile`` module when it is importable
    so multi-workspace isolation keeps working; otherwise falls back to
    environment variables.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from workspace_profile import get_profile_for_cwd  # type: ignore

        profile = get_profile_for_cwd(cwd) or {}
    except Exception:
        profile = {}

    token_env = profile.get("plane_token_env", "PLANE_API_KEY")
    token = (
        profile.get("plane_token")
        or os.environ.get(token_env)
        or os.environ.get("PLANE_API_KEY")
        or os.environ.get("DGS_PLANE_API_KEY")
    )
    return {
        "plane_host": (profile.get("plane_host") or os.environ.get("PLANE_HOST", "")).rstrip("/"),
        "token": token,
        "workspace_slug": profile.get("workspace_name") or os.environ.get("PLANE_WORKSPACE", ""),
        "default_project": profile.get("default_project") or os.environ.get("PLANE_PROJECT"),
    }


def html_to_text(raw):
    """Flatten Plane ``description_html`` into matchable plain text.

    Plane populates ``description_html`` for API-created issues but leaves
    ``description_stripped`` empty, so title/body matching must read the HTML.
    """
    if not raw:
        return ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    text = re.sub(r"(?i)</(p|div|li|h[1-6])>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = _html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class PlaneError(RuntimeError):
    pass


class PlaneClient:
    def __init__(self, profile=None, cwd=None, throttle=DEFAULT_THROTTLE, cache_path=None):
        self.profile = profile or resolve_profile(cwd)
        self.throttle = throttle
        self.cache_path = cache_path
        self._cache = None

        missing = [k for k in ("plane_host", "token", "workspace_slug") if not self.profile.get(k)]
        if missing:
            raise PlaneError(
                "incomplete Plane profile, missing: %s "
                "(set PLANE_HOST / PLANE_API_KEY / PLANE_WORKSPACE or configure workspace_profile)"
                % ", ".join(missing)
            )

    # ---------------------------------------------------------------- transport

    def request(self, path, method="GET", data=None):
        """Issue one API call, retrying on 429 and throttling every response."""
        url = "%s/api/v1/%s" % (self.profile["plane_host"], path.lstrip("/"))
        headers = {"x-api-key": self.profile["token"], "Content-Type": "application/json"}
        body = json.dumps(data).encode("utf-8") if data is not None else None

        last_error = None
        for attempt in range(MAX_ATTEMPTS):
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    payload = resp.read().decode("utf-8")
                time.sleep(self.throttle)
                return json.loads(payload) if payload else {}
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    wait = RATE_LIMIT_FIRST_WAIT if attempt == 0 else RATE_LIMIT_RETRY_WAIT
                    sys.stderr.write("rate limited, waiting %ds (attempt %d)\n" % (wait, attempt + 1))
                    time.sleep(wait)
                    last_error = exc
                    continue
                raise PlaneError("HTTP %s on %s %s: %s" % (exc.code, method, path, exc.reason))
            except urllib.error.URLError as exc:
                raise PlaneError("cannot reach %s: %s" % (url, exc.reason))
        raise PlaneError("rate limit not cleared after %d attempts: %s" % (MAX_ATTEMPTS, last_error))

    # ------------------------------------------------------------------ reading

    def _project_path(self, project_id, suffix=""):
        return "workspaces/%s/projects/%s/%s" % (
            self.profile["workspace_slug"],
            project_id,
            suffix.lstrip("/"),
        )

    def list_issues(self, project_id, use_cache=True):
        """Return every issue of a project, following pagination.

        One batched listing replaces the per-issue GET loop that made bulk
        reconciliation hit the rate limit.
        """
        if use_cache:
            cached = self._cache_get(project_id)
            if cached is not None:
                return cached

        issues = []
        cursor = "%d:0:0" % PAGE_SIZE
        while True:
            page = self.request(self._project_path(project_id, "issues/?cursor=%s" % cursor))
            results = page.get("results", page if isinstance(page, list) else [])
            issues.extend(results)
            next_cursor = page.get("next_cursor") if isinstance(page, dict) else None
            if not next_cursor or not page.get("next_page_results"):
                break
            cursor = next_cursor

        if use_cache:
            self._cache_put(project_id, issues)
        return issues

    def list_states(self, project_id):
        page = self.request(self._project_path(project_id, "states/"))
        return page.get("results", page if isinstance(page, list) else [])

    def terminal_state_ids(self, project_id):
        """State ids whose group ends an issue (completed / cancelled)."""
        return {
            s["id"]: s.get("group")
            for s in self.list_states(project_id)
            if s.get("group") in ("completed", "cancelled")
        }

    # ------------------------------------------------------------------ writing

    def patch_issue(self, project_id, issue_id, payload):
        return self.request(
            self._project_path(project_id, "issues/%s/" % issue_id), method="PATCH", data=payload
        )

    def issue_url(self, project_id, issue_id):
        return "%s/%s/projects/%s/issues/%s" % (
            self.profile["plane_host"],
            self.profile["workspace_slug"],
            project_id,
            issue_id,
        )

    # -------------------------------------------------------------------- cache

    def _load_cache(self):
        if self._cache is None:
            self._cache = {}
            if self.cache_path and os.path.exists(self.cache_path):
                try:
                    with open(self.cache_path, encoding="utf-8") as fh:
                        self._cache = json.load(fh)
                except (OSError, ValueError):
                    self._cache = {}
        return self._cache

    def _cache_get(self, project_id):
        if not self.cache_path:
            return None
        return self._load_cache().get(project_id)

    def _cache_put(self, project_id, issues):
        if not self.cache_path:
            return
        cache = self._load_cache()
        cache[project_id] = issues
        tmp = self.cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False)
        os.replace(tmp, self.cache_path)


def main(argv=None):
    """Smoke check: print issue counts per project id given on the CLI."""
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        profile = resolve_profile()
        print(json.dumps({k: bool(v) if k == "token" else v for k, v in profile.items()}, indent=2))
        return 0
    client = PlaneClient()
    for project_id in argv:
        print("%s: %d issues" % (project_id, len(client.list_issues(project_id, use_cache=False))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
