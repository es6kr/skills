"""Workspace-profile resolution guards for the plane-backlog scripts.

These cover a defect class where the scripts delegated profile resolution to a
symbol that does not exist (`workspace_profile.get_profile_for_cwd`), swallowed
the resulting ImportError, and silently degraded to environment-variable-only
resolution. The practical effect was that per-workspace isolation never engaged
and a run could target a different workspace's Plane project.
"""

import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PLANE_BACKLOG_SCRIPTS = REPO_ROOT / "skills" / "plane-backlog" / "scripts"
FIX_PLAN_SCRIPTS = REPO_ROOT / "skills" / "fix-plan" / "scripts"

# Scripts that must never carry a concrete workspace identifier as a fallback.
#
# Both skill directories are listed because the docs reference the create
# scripts under either root, and a copy may exist in one, the other, or both.
# Only the paths that actually resolve are asserted on — a missing candidate is
# a documentation drift to fix in the docs, not a reason to fail this guard with
# a FileNotFoundError that says nothing about workspace identifiers.
_CREATE_SCRIPT_CANDIDATES = [
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
    f"{PLANE_BACKLOG_SCRIPTS} or {FIX_PLAN_SCRIPTS} — "
    "the scripts moved and this test's candidate list needs updating"
)

UUID_LITERAL = re.compile(
    r"['\"][0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}['\"]"
)
PLANE_HOST_LITERAL = re.compile(r"['\"]https?://[^'\"]*plane[^'\"]*['\"]")


@pytest.fixture
def scripts_on_path(monkeypatch):
    for d in (PLANE_BACKLOG_SCRIPTS, FIX_PLAN_SCRIPTS):
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


def test_workspace_profile_exposes_the_symbol_the_scripts_import(scripts_on_path):
    """The delegation target must actually exist in workspace_profile."""
    import workspace_profile

    source = "\n".join(
        p.read_text(encoding="utf-8")
        for p in list(CREATE_SCRIPTS) + [PLANE_BACKLOG_SCRIPTS / "plane_client.py"]
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
