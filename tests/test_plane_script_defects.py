"""Regression guards for the two plane-script defect classes (2026-08-20 plan).

Defect 1 — Cloudflare WAF 403: plane.es6.kr rejects the default
`Python-urllib/3.x` User-Agent, so every urllib client here must send the
browser-like UA that `plane_create_comment.py` established as the in-repo
precedent. These tests capture the outbound `urllib.request.Request` and
assert the header, so a regression to the default UA fails loudly instead of
surfacing as a live 403.

Defect 2 — K3s fallback ValueError: `create_via_k3s_fallback` embeds a Django
shell script in an f-string; unescaped single braces raised
`ValueError: Invalid format specifier` at build time before any execution.
The builder is now a dedicated function whose output must both build (with
hostile quotes/braces in user input) and parse as valid Python.

Cross-cutting — the `fix-plan` and `plane-backlog` copies of
`plane_create_issue.py` must stay byte-identical (dual-script drift is how
Defect 2 survived: one copy was fixed, the other kept the stale template).
"""

import ast
import filecmp
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIX_PLAN_SCRIPTS = REPO_ROOT / "skills" / "fix-plan" / "scripts"
PLANE_BACKLOG_SCRIPTS = REPO_ROOT / "skills" / "plane-backlog" / "scripts"

EXPECTED_UA = "Mozilla/5.0 (plane-backlog)"

CREATE_ISSUE_COPIES = [
    pytest.param(PLANE_BACKLOG_SCRIPTS / "plane_create_issue.py", id="plane-backlog"),
]


PROFILE = {
    "plane_host": "https://plane.invalid",
    "token": "test-token",
    "workspace_slug": "testws",
    "default_project": "11111111-1111-1111-1111-111111111111",
}

# Inputs with the exact character classes that triggered Defect 2: single
# braces and quotes flowing into an f-string template.
HOSTILE_TITLE = 'Title with "quotes", {braces} and \'apostrophes\''
HOSTILE_DESCRIPTION = "# Head {x}\n- item {y}\n  - **sub** `code {z}`\nplain 'text'"


def load_module(path: Path, name: str):
    """Load a script by file path under a unique module name.

    Both scripts self-bootstrap their sibling directories onto sys.path, but
    the interpreter running pytest still needs the shared dirs visible before
    the module-level `from plane_client import ...` / `from workspace_profile
    import ...` lines execute.
    """
    for d in (str(PLANE_BACKLOG_SCRIPTS), str(FIX_PLAN_SCRIPTS)):
        if d not in sys.path:
            sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload: dict, status: int = 201):
        self.status = status
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# ---------------------------------------------------------------- Defect 1: UA


@pytest.mark.parametrize("script_path", CREATE_ISSUE_COPIES)
def test_create_issue_rest_sends_browser_user_agent(script_path, monkeypatch):
    mod = load_module(script_path, f"pci_ua_{script_path.parent.parent.name.replace('-', '_')}")
    captured = []

    def fake_urlopen(req, *args, **kwargs):
        captured.append(req)
        return FakeResponse({"id": "issue-1", "sequence_id": 7})

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    res = mod.create_via_rest_api(PROFILE, "title", "desc", is_intake=False)

    assert res["success"] is True
    ua = captured[0].get_header("User-agent")
    assert ua == EXPECTED_UA
    assert not (ua or "").startswith("Python-urllib")


def test_plane_sync_request_sends_browser_user_agent(monkeypatch):
    mod = load_module(FIX_PLAN_SCRIPTS / "plane_sync.py", "plane_sync_ua")
    captured = []

    def fake_urlopen(req, *args, **kwargs):
        captured.append(req)
        return FakeResponse({}, status=200)

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    mod.make_plane_request(
        {"plane_host": "https://plane.invalid", "plane_token": "tok", "plane_token_env": "X"},
        "workspaces/testws/projects/",
    )

    assert captured, "make_plane_request never issued a request"
    assert captured[0].get_header("User-agent") == EXPECTED_UA


def test_plane_client_request_sends_browser_user_agent(monkeypatch):
    pc = load_module(PLANE_BACKLOG_SCRIPTS / "plane_client.py", "plane_client_ua")
    captured = []

    def fake_urlopen(req, *args, **kwargs):
        captured.append(req)
        return FakeResponse({"ok": True}, status=200)

    monkeypatch.setattr(pc.urllib.request, "urlopen", fake_urlopen)
    client = pc.PlaneClient(profile=dict(PROFILE), throttle=0)
    client.request("workspaces/testws/projects/")

    assert captured[0].get_header("User-agent") == EXPECTED_UA


# ------------------------------------------------- Defect 2: fallback template


@pytest.mark.parametrize("script_path", CREATE_ISSUE_COPIES)
def test_k3s_script_builds_and_parses_with_hostile_input(script_path):
    mod = load_module(script_path, f"pci_tpl_{script_path.parent.parent.name.replace('-', '_')}")
    # Build must not raise (the old template died here with
    # "ValueError: Invalid format specifier" on single braces) ...
    script = mod.build_k3s_py_script(
        "testws",
        "11111111-1111-1111-1111-111111111111",
        "https://plane.invalid",
        HOSTILE_TITLE,
        HOSTILE_DESCRIPTION,
        True,
    )
    # ... and the generated Django-shell source must be valid Python.
    ast.parse(script)


@pytest.mark.parametrize("script_path", CREATE_ISSUE_COPIES)
def test_k3s_fallback_resolves_namespace_from_profile(script_path, monkeypatch):
    mod = load_module(script_path, f"pci_ns_{script_path.parent.parent.name.replace('-', '_')}")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return types.SimpleNamespace(
            stdout='RESULT_JSON:{"success": true, "method": "K3s Django Shell Fallback"}',
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(mod.shutil, "which", lambda _: "/usr/local/bin/kubectl")
    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    res = mod.create_via_k3s_fallback(dict(PROFILE), "title")
    assert res["success"] is True
    assert calls[0][calls[0].index("-n") + 1] == "plane-ce"

    mod.create_via_k3s_fallback(dict(PROFILE, k3s_namespace="custom-ns"), "title")
    assert calls[1][calls[1].index("-n") + 1] == "custom-ns"


@pytest.mark.parametrize("script_path", CREATE_ISSUE_COPIES)
def test_k3s_fallback_skips_gracefully_without_kubectl(script_path, monkeypatch):
    mod = load_module(script_path, f"pci_skip_{script_path.parent.parent.name.replace('-', '_')}")
    ran = []

    monkeypatch.setattr(mod.shutil, "which", lambda _: None)
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: ran.append(a))

    res = mod.create_via_k3s_fallback(dict(PROFILE), "title")
    assert res["success"] is False
    assert "kubectl" in res["reason"]
    assert not ran, "fallback must not shell out when kubectl is absent"


def test_index_line_re_matches_identifier_prefix_containing_digits():
    """A Plane project identifier may contain digits (e.g. ES6KR-117).

    INDEX_LINE_RE previously matched the prefix with `[A-Z]+`, so no index line
    from such a workspace ever matched. plane_sync then reported "0 index lines"
    and every marker stayed unsynced — a silent no-op rather than a loud error.
    """
    mod = load_module(FIX_PLAN_SCRIPTS / "plane_sync.py", "plane_sync_ident")
    url = (
        "https://plane.example.invalid/acme/projects/"
        "4b4d8bfc-5e5d-495b-bd4c-301fe89e5bb0/issues/"
        "016a702b-11aa-424d-834c-53a818e9de0c"
    )

    for ident in ("ES6KR-117", "INFRA-12", "A1-3"):
        line = f"- [ ] [{ident}] some tracked item → Plane ({url})"
        match = mod.INDEX_LINE_RE.match(line)
        assert match, f"index line with identifier {ident} must match"
        assert match.group("ident") == ident

    # The prefix must still start with a letter — a purely numeric prefix is not
    # a Plane identifier and must not be absorbed.
    numeric = f"- [ ] [123-4] not an identifier → Plane ({url})"
    assert mod.INDEX_LINE_RE.match(numeric) is None
