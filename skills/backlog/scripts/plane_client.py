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

# plane.es6.kr sits behind Cloudflare, which 403s the default `Python-urllib`
# User-Agent. A browser-like User-Agent header is required — same constant as
# plane_create_comment.py, the in-repo precedent that already clears the WAF.
UA = "Mozilla/5.0 (plane-backlog)"
PAGE_SIZE = 100

# fix_plan `[BLOCKED:P0-P3:...]` marker <-> Plane native `priority` field.
# Single source of truth — plane_create_issue.py and plane_sync.py both
# import this instead of re-declaring the mapping (drift class already hit
# once this session with the two plane_create_issue.py copies).
MARKER_TO_PRIORITY = {
    "P0": "urgent",
    "P1": "high",
    "P2": "medium",
    "P3": "low",
}
PRIORITY_TO_MARKER = {native: marker for marker, native in MARKER_TO_PRIORITY.items()}
VALID_PLANE_PRIORITIES = frozenset(MARKER_TO_PRIORITY.values()) | {"none"}


def normalize_priority(value):
    """Normalize a priority value to one of Plane's native priority strings.

    Accepts case-insensitive P-tags (``p0``/``P0`` ... ``p3``/``P3``), Plane's
    own native values (``urgent``/``high``/``medium``/``low``/``none``), or a
    falsy value (treated as ``"none"``). Raises ``ValueError`` on anything
    else — a typo in ``--priority`` should fail loudly, not silently post an
    issue with no priority set.
    """
    if not value:
        return "none"
    text = str(value).strip()
    upper = text.upper()
    if upper in MARKER_TO_PRIORITY:
        return MARKER_TO_PRIORITY[upper]
    lower = text.lower()
    if lower in VALID_PLANE_PRIORITIES:
        return lower
    raise ValueError(
        f"unrecognized priority {value!r} — expected one of P0-P3 "
        f"(case-insensitive) or {sorted(VALID_PLANE_PRIORITIES)}"
    )


def priority_to_marker(native_priority):
    """Reverse of normalize_priority: Plane native value -> P0-P3 marker.

    Returns ``None`` for ``"none"`` or an unrecognized value — callers decide
    whether the absence of a marker is itself meaningful.
    """
    return PRIORITY_TO_MARKER.get((native_priority or "").strip().lower())


def _workspace_profile_dirs():
    """Directories that may hold ``workspace_profile.py``, most specific first.

    The module ships with the ``fix-plan`` skill, so a script living under
    ``plane-backlog/scripts`` cannot reach it by adding only its own directory.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    candidates = [
        here,
        os.path.join(plugin_root, "skills", "fix-plan", "scripts") if plugin_root else "",
        os.path.abspath(os.path.join(here, os.pardir, os.pardir, "fix-plan", "scripts")),
    ]
    return [d for d in candidates if d and os.path.isdir(d)]


def resolve_profile(cwd=None):
    """Return the workspace profile dict (plane_host / token / slug / project).

    Delegates to the ``workspace_profile`` module so multi-workspace isolation
    keeps working. A failure to reach it is reported on stderr rather than
    silently degrading to environment variables — a configuration error and
    "no profile configured" are not the same thing, and conflating them lets a
    run target the wrong workspace without any signal.
    """
    for candidate in _workspace_profile_dirs():
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
    try:
        from workspace_profile import get_profile  # type: ignore

        profile = get_profile(target_path=cwd) or {}
    except ImportError as exc:
        print(
            f"WARN: workspace_profile unavailable ({exc}); "
            "resolving from environment variables only — per-workspace "
            "isolation is INACTIVE for this run",
            file=sys.stderr,
        )
        profile = {}

    # Token precedence: the profile-resolved token (workspace_profile.get_profile
    # sources it from the profile's token_env / PLANE_API_KEY / token_file), then
    # the generic env keys. A previous hardcoded `DGS_PLANE_API_KEY` tail was
    # removed: baking one specific workspace's env var into this vendor-agnostic
    # client silently routed *other* workspaces' calls out under the wrong key
    # whenever their own token was unset (HTTP 403 "token is not valid"),
    # defeating the per-workspace isolation this client is supposed to enforce.
    token_env = profile.get("plane_token_env", "PLANE_API_KEY")
    token = (
        profile.get("plane_token")
        or os.environ.get(token_env)
        or os.environ.get("PLANE_API_KEY")
    )
    return {
        "plane_host": (profile.get("plane_host") or os.environ.get("PLANE_HOST", "")).rstrip("/"),
        "token": token,
        "workspace_slug": profile.get("workspace_slug") or os.environ.get("PLANE_WORKSPACE") or profile.get("workspace_name", ""),
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


def format_browse_url(plane_host, workspace_slug, identifier, sequence_id):
    """Human-facing URL: https://<host>/<workspace_slug>/browse/<IDENTIFIER>-<SEQ>.

    Module-level so callers that never instantiate ``PlaneClient`` (e.g.
    scripts that hand-roll their own urllib requests) can still produce the
    standard reporting URL instead of a project-UUID-nested API URL. See
    ``PlaneClient.browse_url`` for the instance-method form.
    """
    return "%s/%s/browse/%s-%s" % (
        plane_host.rstrip("/"),
        workspace_slug,
        identifier,
        sequence_id,
    )


def fetch_project_identifier(plane_host, workspace_slug, token, project_id, user_agent=None):
    """One-off GET for a project's short code (e.g. "INFRA") given its UUID.

    Standalone (no ``PlaneClient`` instance) for callers — like
    ``plane_create_issue.py``'s REST path — that build requests with their own
    ``urllib.request`` calls rather than through the class. Returns ``None`` on
    any failure; callers should fall back to the raw ``issue_url`` in that case
    rather than raising, since this is only needed to build a nicer report URL.
    """
    url = "%s/api/v1/workspaces/%s/projects/%s/" % (plane_host.rstrip("/"), workspace_slug, project_id)
    headers = {"User-Agent": user_agent or UA}
    req = urllib.request.Request(url, headers=headers, method="GET")
    req.add_unredirected_header("x-api-key", token)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("identifier")
    except Exception:
        return None


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
        headers = {"x-api-key": self.profile["token"], "Content-Type": "application/json", "User-Agent": UA}
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

    def list_projects(self):
        """Return every project in the workspace (id, identifier, name, ...), following pagination.

        Used to resolve a short project code (e.g. "ES6KR") to its project_id
        before an identifier-based lookup — see plane_verify_identifier.py.
        Not cached: the project list is small and rarely called in a loop.
        """
        projects = []
        cursor = "%d:0:0" % PAGE_SIZE
        while True:
            page = self.request(
                "workspaces/%s/projects/?cursor=%s" % (self.profile["workspace_slug"], cursor)
            )
            if isinstance(page, list):
                return page
            results = page.get("results", [])
            projects.extend(results)
            next_cursor = page.get("next_cursor")
            if not next_cursor or not page.get("next_page_results"):
                break
            cursor = next_cursor
        return projects

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
        """Internal API-shaped URL (project UUID + issue UUID).

        Not for human-facing reports or chat/comment output — Plane resolves
        this fine, but it embeds implementation UUIDs a reader can't act on.
        Use ``browse_url`` wherever the link is meant to be read or clicked.
        """
        return "%s/%s/projects/%s/issues/%s" % (
            self.profile["plane_host"],
            self.profile["workspace_slug"],
            project_id,
            issue_id,
        )

    def browse_url(self, identifier, sequence_id):
        """Human-facing URL: https://<host>/<workspace_slug>/browse/<IDENTIFIER>-<SEQ>.

        ``identifier`` is the project's short code (e.g. "INFRA"), ``sequence_id``
        the issue's per-project sequence number (e.g. 62) — both already present
        on any issue/project payload this client returns. Use this, not
        ``issue_url``, for anything a person will read or click.
        """
        return format_browse_url(
            self.profile["plane_host"], self.profile["workspace_slug"], identifier, sequence_id
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
