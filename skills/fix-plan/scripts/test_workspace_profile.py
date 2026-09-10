#!/usr/bin/env python3
"""
Unit tests for `resolve_tracker_root()` in workspace_profile.py (Issue #262).

resolve_tracker_root() has been wired into 6 fix-plan skill scripts since PR
#255 (detect_bloated_tasks, stale_check, cleanup, plane_sync,
fable_queue_replenish, artifact_post_ingest) but had zero direct unit
coverage of its own 4-tier priority (env var > profile config > auto-detect
> default) until now.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

import importlib.util
spec = importlib.util.spec_from_file_location("workspace_profile", str(SCRIPT_DIR / "workspace_profile.py"))
workspace_profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace_profile)


class TestResolveTrackerRoot(unittest.TestCase):
    def test_env_var_override_wins_over_everything(self):
        with mock.patch.dict(os.environ, {"FIXPLAN_TRACKER_ROOT": ".custom"}):
            with tempfile.TemporaryDirectory() as d:
                # Even with a real .agents/fix_plan.md present, the env var wins.
                p = Path(d) / ".agents"
                p.mkdir()
                (p / "fix_plan.md").write_text("x", encoding="utf-8")
                self.assertEqual(workspace_profile.resolve_tracker_root(d), ".custom")

    def test_auto_detect_prefers_agents_when_both_exist(self):
        with tempfile.TemporaryDirectory() as d:
            for sub in (".agents", ".ralph"):
                p = Path(d) / sub
                p.mkdir()
                (p / "fix_plan.md").write_text("x", encoding="utf-8")
            with mock.patch.object(workspace_profile, "load_user_config", return_value={}):
                self.assertEqual(workspace_profile.resolve_tracker_root(d), ".agents")

    def test_auto_detect_falls_back_to_ralph_when_only_ralph_has_fix_plan(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".ralph"
            p.mkdir()
            (p / "fix_plan.md").write_text("x", encoding="utf-8")
            with mock.patch.object(workspace_profile, "load_user_config", return_value={}):
                self.assertEqual(workspace_profile.resolve_tracker_root(d), ".ralph")

    def test_default_fallback_when_neither_root_has_fix_plan(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(workspace_profile, "load_user_config", return_value={}):
                self.assertEqual(workspace_profile.resolve_tracker_root(d), ".ralph")

    def test_explicit_profile_config_wins_over_auto_detect(self):
        with tempfile.TemporaryDirectory() as d:
            # Filesystem would auto-detect ".agents", but the profile's
            # explicit tracker_root ("checklist-root") must win instead.
            p = Path(d) / ".agents"
            p.mkdir()
            (p / "fix_plan.md").write_text("x", encoding="utf-8")
            fake_config = {
                "profiles": {
                    "myworkspace": {"tracker_root": "checklist-root"}
                }
            }
            with mock.patch.object(workspace_profile, "load_user_config", return_value=fake_config):
                self.assertEqual(
                    workspace_profile.resolve_tracker_root(d, workspace_name="myworkspace"),
                    "checklist-root",
                )


class TestBacklogTokenAndSlugResolution(unittest.TestCase):
    """token_file + workspace_slug must survive the v2->flat translation and
    feed get_profile's token resolution.

    Regression: v2_profile_to_flat dropped both keys, so the Plane token was
    never loaded from its file (resolution leaked to whatever generic env key
    was set — the wrong workspace's) and the slug fell back to the profile
    name (e.g. `es6kr_skills` instead of its real slug `es6kr`).
    """

    def test_v2_flat_carries_workspace_slug_and_token_file(self):
        profile = {
            "roles": {
                "backlog": {
                    "kind": "plane",
                    "endpoint": "https://plane.example.com",
                    "workspace_slug": "acme",
                    "token_env": "ACME_PLANE_API_KEY",
                    "token_file": "/tmp/acme-token.txt",
                    "project": "proj-1",
                }
            }
        }
        flat = workspace_profile.v2_profile_to_flat(profile, {})
        self.assertEqual(flat["workspace_slug"], "acme")
        self.assertEqual(flat["token_file"], "/tmp/acme-token.txt")

    def test_get_profile_loads_token_from_file_when_env_unset(self):
        with tempfile.TemporaryDirectory() as d:
            tok = Path(d) / "token.txt"
            tok.write_text("file-token-123\n", encoding="utf-8")  # trailing newline must be stripped
            fake_config = {
                "profiles": {
                    "acme": {
                        "workspace_name": "acme",
                        "plane_host": "https://plane.example.com",
                        "plane_token_env": "ACME_PLANE_API_KEY",
                        "workspace_slug": "acme",
                        "token_file": str(tok),
                    }
                }
            }
            with mock.patch.object(workspace_profile, "load_user_config", return_value=fake_config):
                with mock.patch.dict(os.environ, {}, clear=True):
                    profile = workspace_profile.get_profile(workspace_name="acme")
            self.assertEqual(profile["plane_token"], "file-token-123")
            self.assertEqual(profile["workspace_slug"], "acme")

    def test_env_var_overrides_token_file(self):
        with tempfile.TemporaryDirectory() as d:
            tok = Path(d) / "token.txt"
            tok.write_text("file-token-123", encoding="utf-8")
            fake_config = {
                "profiles": {
                    "acme": {
                        "workspace_name": "acme",
                        "plane_host": "https://plane.example.com",
                        "plane_token_env": "ACME_PLANE_API_KEY",
                        "token_file": str(tok),
                    }
                }
            }
            with mock.patch.object(workspace_profile, "load_user_config", return_value=fake_config):
                with mock.patch.dict(os.environ, {"ACME_PLANE_API_KEY": "env-token-xyz"}, clear=True):
                    profile = workspace_profile.get_profile(workspace_name="acme")
            self.assertEqual(profile["plane_token"], "env-token-xyz")

    def test_missing_token_file_degrades_to_empty_not_crash(self):
        fake_config = {
            "profiles": {
                "acme": {
                    "workspace_name": "acme",
                    "plane_host": "https://plane.example.com",
                    "plane_token_env": "ACME_PLANE_API_KEY",
                    "token_file": "/nonexistent/path/token.txt",
                }
            }
        }
        with mock.patch.object(workspace_profile, "load_user_config", return_value=fake_config):
            with mock.patch.dict(os.environ, {}, clear=True):
                profile = workspace_profile.get_profile(workspace_name="acme")
        self.assertEqual(profile["plane_token"], "")


if __name__ == "__main__":
    unittest.main()
