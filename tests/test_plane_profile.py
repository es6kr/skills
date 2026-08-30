"""Workspace-profile resolution guards for the plane-backlog scripts.

These cover a defect class where the scripts delegated profile resolution to a
symbol that does not exist (`workspace_profile.get_profile_for_cwd`), swallowed
the resulting ImportError, and silently degraded to environment-variable-only
resolution. The practical effect was that per-workspace isolation never engaged
and a run could target a different workspace's Plane project.
"""

import ast
import base64
import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PLANE_BACKLOG_SCRIPTS = REPO_ROOT / "skills" / "plane-backlog" / "scripts"
BACKLOG_SCRIPTS = REPO_ROOT / "skills" / "backlog" / "scripts"
FIX_PLAN_SCRIPTS = REPO_ROOT / "skills" / "fix-plan" / "scripts"

# Scripts that must never carry a concrete workspace identifier as a fallback.
#
# All skill directories are listed because the docs reference the create
# scripts under either root, and a copy may exist in one, the other, or both.
# Only the paths that actually resolve are asserted on — a missing candidate is
# a documentation drift to fix in the docs, not a reason to fail this guard with
# a FileNotFoundError that says nothing about workspace identifiers.
_CREATE_SCRIPT_CANDIDATES = [
    BACKLOG_SCRIPTS / "plane_create_issue.py",
    BACKLOG_SCRIPTS / "plane_create_comment.py",
    PLANE_BACKLOG_SCRIPTS / "plane_create_issue.py",
    PLANE_BACKLOG_SCRIPTS / "plane_create_comment.py",
    FIX_PLAN_SCRIPTS / "plane_create_issue.py",
    FIX_PLAN_SCRIPTS / "plane_create_comment.py",
]

CREATE_SCRIPTS = [p for p in _CREATE_SCRIPT_CANDIDATES if p.is_file()]

# Guard the guard: if a rename empties the list, every test below would pass
# vacuously and the workspace-identifier check would silently stop running.
assert CREATE_SCRIPTS, (
    "no create script resolved under "
    f"{BACKLOG_SCRIPTS}, {PLANE_BACKLOG_SCRIPTS} or {FIX_PLAN_SCRIPTS} — "
    "the scripts moved and this test's candidate list needs updating"
)

UUID_LITERAL = re.compile(
    r"['\"][0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}['\"]"
)
PLANE_HOST_LITERAL = re.compile(r"['\"]https?://[^'\"]*plane[^'\"]*['\"]")


@pytest.fixture
def scripts_on_path(monkeypatch):
    for d in (BACKLOG_SCRIPTS, PLANE_BACKLOG_SCRIPTS, FIX_PLAN_SCRIPTS):
        if d.is_dir():
            monkeypatch.syspath_prepend(str(d))
    # Drop cached imports so each test gets a clean module state.
    for name in ("plane_client", "workspace_profile"):
        sys.modules.pop(name, None)
    yield
    for name in ("plane_client", "workspace_profile"):
        sys.modules.pop(name, None)


@pytest.fixture
def isolated_workspace(tmp_path, monkeypatch, scripts_on_path):
    """A throwaway workspace plus a config.json that maps to it.

    Returns (workspace_dir, expected_profile).
    """
    workspace = tmp_path / "acme-workspace"
    (workspace / ".agents").mkdir(parents=True)
    (workspace / ".agents" / "fix_plan.md").write_text("# tracker\n", encoding="utf-8")

    expected = {
        "cwd_match": ["acme-workspace"],
        "plane_host": "https://plane.acme.invalid",
        "default_project": "acme-project",
        "workspace_name": "acme",
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"profiles": {"acme": expected}}), encoding="utf-8"
    )

    import workspace_profile

    monkeypatch.setattr(workspace_profile, "CONFIG_FILE", config_file)
    monkeypatch.setattr(
        workspace_profile, "CONFIG_FILE_V2", tmp_path / "no-agent-workspace.json"
    )

    # Environment must not be able to satisfy the assertions on its own.
    for var in (
        "PLANE_HOST",
        "PLANE_WORKSPACE",
        "PLANE_PROJECT",
        "PLANE_WORKSPACE_PROFILE",
        "FIXPLAN_TRACKER_ROOT",
    ):
        monkeypatch.delenv(var, raising=False)

    return workspace, expected


def test_resolve_profile_reaches_workspace_config(isolated_workspace):
    """resolve_profile() must consult the workspace profile, not just the environment."""
    workspace, expected = isolated_workspace

    import plane_client

    profile = plane_client.resolve_profile(str(workspace))

    assert profile["plane_host"] == expected["plane_host"], (
        "plane_host did not come from the workspace profile — the workspace_profile "
        "delegation is not reached, so per-workspace isolation is inactive"
    )
    assert profile["workspace_slug"] == expected["workspace_name"]
    assert profile["default_project"] == expected["default_project"]


def test_workspace_profile_resolves_artifacts_path(tmp_path, monkeypatch, scripts_on_path):
    """workspace_profile must resolve artifacts_path from v2 config and provide defaults."""
    import workspace_profile

    v2_config_file = tmp_path / "agent-workspace.json"
    v2_config_file.write_text(
        json.dumps({
            "version": 2,
            "defaults": {
                "artifacts": {"kind": "dir", "path": ".agents/docs/generated"}
            },
            "profiles": {
                "custom_ws": {
                    "match": {"path_components": ["custom_ws"]},
                    "roles": {
                        "artifacts": {"kind": "dir", "path": "custom/docs/path"}
                    }
                },
                "default_ws": {
                    "match": {"path_components": ["default_ws"]},
                    "roles": {}
                }
            }
        }),
        encoding="utf-8"
    )

    monkeypatch.setattr(workspace_profile, "CONFIG_FILE_V2", v2_config_file)
    monkeypatch.setattr(workspace_profile, "CONFIG_FILE", tmp_path / "no-v1.json")

    prof_custom = workspace_profile.get_profile(workspace_name="custom_ws")
    assert prof_custom["artifacts_path"] == "custom/docs/path"

    prof_default = workspace_profile.get_profile(workspace_name="default_ws")
    assert prof_default["artifacts_path"] == ".agents/docs/generated"



def test_workspace_profile_exposes_the_symbol_the_scripts_import(scripts_on_path):
    """The delegation target must actually exist in workspace_profile."""
    import workspace_profile

    client_scripts = [p for p in (BACKLOG_SCRIPTS / "plane_client.py", PLANE_BACKLOG_SCRIPTS / "plane_client.py") if p.is_file()]
    source = "\n".join(
        p.read_text(encoding="utf-8")
        for p in list(CREATE_SCRIPTS) + client_scripts
    )
    for symbol in re.findall(r"from workspace_profile import (\w+)", source):
        assert hasattr(workspace_profile, symbol), (
            f"scripts import workspace_profile.{symbol}, which does not exist — "
            "the ImportError is swallowed and resolution degrades silently"
        )


def test_import_failure_is_reported_not_swallowed(
    isolated_workspace, monkeypatch, capsys
):
    """A missing workspace_profile must warn, not degrade in silence."""
    workspace, _ = isolated_workspace

    import plane_client

    # Make the delegation target unimportable for this call only.
    monkeypatch.setitem(sys.modules, "workspace_profile", None)

    plane_client.resolve_profile(str(workspace))

    assert "workspace_profile" in capsys.readouterr().err, (
        "profile resolution fell back to environment variables without reporting "
        "why — a configuration error is indistinguishable from 'no profile set'"
    )


@pytest.mark.parametrize("script", CREATE_SCRIPTS, ids=lambda p: p.name)
def test_no_hardcoded_workspace_identifier_fallback(script):
    """No concrete project UUID or Plane host may be baked in as a fallback.

    A hardcoded identifier turns a failed profile lookup into a silent write
    against somebody else's workspace.
    """
    source = script.read_text(encoding="utf-8")

    assert not UUID_LITERAL.search(source), (
        f"{script.name} embeds a concrete project UUID; a profile miss would "
        "silently target that project"
    )
    assert not PLANE_HOST_LITERAL.search(source), (
        f"{script.name} embeds a concrete Plane host; a profile miss would "
        "silently target that deployment"
    )


def test_k3s_fallback_script_survives_quote_in_workspace_slug(monkeypatch):
    """workspace_slug/project_id must not break out of the generated py_script.

    `create_via_k3s_fallback` builds a Django-shell Python script as an
    f-string and interpolates the profile's workspace_slug and the resolved
    project id directly into it. Prior to the json.dumps fix, both were
    embedded as raw text inside single-quoted Python literals
    (`filter(slug='{workspace_slug}')`), so a value containing a single quote
    generated syntactically invalid — or attacker-controlled — Python source
    that plane-api would then execute via `manage.py shell`.

    Loaded by explicit file path (not via scripts_on_path/sys.path) because
    both the plane-backlog and fix-plan copies share the module name
    "plane_create_issue" — only the plane-backlog copy carries this fix.
    """
    import importlib.util

    target_script = (
        BACKLOG_SCRIPTS / "plane_create_issue.py"
        if (BACKLOG_SCRIPTS / "plane_create_issue.py").is_file()
        else PLANE_BACKLOG_SCRIPTS / "plane_create_issue.py"
    )
    spec = importlib.util.spec_from_file_location(
        "plane_create_issue_under_test",
        target_script,
    )
    plane_create_issue = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plane_create_issue)

    captured_cmd = {}

    class _FakeCompletedProcess:
        stdout = 'RESULT_JSON:{"success": true, "id": "1", "sequence_id": 1, "title": "t", "url": "u", "intake": true}\n'
        stderr = ""

    def _fake_run(cmd, capture_output, text, check):
        captured_cmd["cmd"] = cmd
        return _FakeCompletedProcess()

    monkeypatch.setattr(plane_create_issue.shutil, "which", lambda _: "/usr/local/bin/kubectl")
    monkeypatch.setattr(plane_create_issue.subprocess, "run", _fake_run)

    malicious_slug = "acme'; Workspace.objects.all().delete(); x='"
    profile = {
        "workspace_slug": malicious_slug,
        "plane_host": "https://plane.acme.invalid",
    }

    plane_create_issue.create_via_k3s_fallback(
        profile, title="regression test", project_id="proj-1"
    )

    assert captured_cmd, "subprocess.run was never called — fallback path did not run"
    shell_cmd = captured_cmd["cmd"][-1]
    b64_marker = "base64.b64decode('"
    start = shell_cmd.index(b64_marker) + len(b64_marker)
    end = shell_cmd.index("'", start)
    py_script = base64.b64decode(shell_cmd[start:end]).decode("utf-8")

    ast.parse(py_script)  # raises SyntaxError if the slug broke out of the literal

    filter_line = next(
        line for line in py_script.splitlines() if "Workspace.objects.filter" in line
    )
    assert filter_line.strip() == (
        f"ws = Workspace.objects.filter(slug={json.dumps(malicious_slug)}).first()"
    ), (
        "the slug must be embedded via json.dumps, not raw-interpolated into a "
        "single-quoted literal — otherwise its own quote characters break out "
        "of the string and the trailing text runs as Python statements"
    )
