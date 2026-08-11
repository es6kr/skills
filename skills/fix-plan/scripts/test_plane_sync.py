#!/usr/bin/env python3
"""
Unit tests for `plane_sync.py` (fix-plan skill script).
Covers the Plane index-line parser and the completed/cancelled -> marker
mapping logic added to replace the former connectivity-probe stub.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

import importlib.util
spec = importlib.util.spec_from_file_location("plane_sync", str(SCRIPT_DIR / "plane_sync.py"))
plane_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plane_sync)


PHASE3_LINE = (
    "- [BLOCKED:P3:external] [INFRA-6] title → Plane "
    "(https://plane.example.com/myworkspace/projects/"
    "11111111-1111-1111-1111-111111111111/issues/"
    "22222222-2222-2222-2222-222222222222) *(note)*"
)


class TestParseIndexLines(unittest.TestCase):
    def test_matches_phase3_line(self):
        matches = plane_sync.parse_index_lines([PHASE3_LINE])
        self.assertEqual(len(matches), 1)
        entry = matches[0]
        self.assertEqual(entry["line_no"], 0)
        self.assertEqual(entry["match"].group("marker"), "BLOCKED:P3:external")
        self.assertEqual(entry["url_match"]["workspace"], "myworkspace")
        self.assertEqual(entry["url_match"]["project"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(entry["url_match"]["issue"], "22222222-2222-2222-2222-222222222222")

    def test_ignores_non_plane_lines(self):
        lines = ["- [ ] plain item, no Plane link", "some prose", ""]
        self.assertEqual(plane_sync.parse_index_lines(lines), [])

    def test_ignores_plain_open_marker_line(self):
        line = (
            "- [ ] [SSOWEB-25] title → Plane "
            "(https://plane.example.com/myworkspace/projects/"
            "33333333-3333-3333-3333-333333333333/issues/"
            "44444444-4444-4444-4444-444444444444) *(note)*"
        )
        matches = plane_sync.parse_index_lines([line])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["match"].group("marker"), " ")


class TestComputeUpdates(unittest.TestCase):
    """
    The real Plane REST API v1 issue-detail response has no `state_detail`
    field -- it returns `state` as a bare state-UUID. Resolving that UUID to
    its group (backlog/unstarted/started/completed/cancelled) requires a
    second call to GET .../states/{state_id}/. Discovered via a live
    round-trip check against a real workspace (fixed 2026-08-09) -- the
    earlier `state_detail`-shaped mocks below encoded the wrong API contract
    and never caught this, so compute_updates() silently no-op'd on every
    real issue regardless of its actual state.
    """

    STATE_ID = "55555555-5555-5555-5555-555555555555"

    def _profile(self):
        return {"plane_host": "https://plane.example.com", "plane_token": "tok"}

    def _patch_state(self, group):
        return patch.multiple(
            plane_sync,
            fetch_issue_state=lambda *a, **kw: {"state": self.STATE_ID},
            fetch_state_group=lambda *a, **kw: {"group": group},
        )

    def test_completed_state_updates_marker_to_x(self):
        with self._patch_state("completed"):
            updates = plane_sync.compute_updates([PHASE3_LINE], self._profile())
        self.assertEqual(len(updates), 1)
        self.assertIn("[x]", updates[0]["new"])
        self.assertNotIn("[BLOCKED:P3:external]", updates[0]["new"])

    def test_cancelled_state_updates_marker_to_blocked_external(self):
        with self._patch_state("cancelled"):
            updates = plane_sync.compute_updates([PHASE3_LINE], self._profile())
        self.assertEqual(len(updates), 1)
        self.assertIn("[BLOCKED:P2:external]", updates[0]["new"])

    def test_open_state_no_change(self):
        for group in ("backlog", "unstarted", "started"):
            with self._patch_state(group):
                updates = plane_sync.compute_updates([PHASE3_LINE], self._profile())
            self.assertEqual(updates, [], f"unexpected update for state_group={group}")

    def test_issue_fetch_api_error_no_change(self):
        with patch.object(
            plane_sync, "fetch_issue_state",
            return_value={"error": "timeout"},
        ):
            updates = plane_sync.compute_updates([PHASE3_LINE], self._profile())
        self.assertEqual(updates, [])

    def test_state_fetch_api_error_no_change(self):
        with patch.multiple(
            plane_sync,
            fetch_issue_state=lambda *a, **kw: {"state": self.STATE_ID},
            fetch_state_group=lambda *a, **kw: {"error": "timeout"},
        ):
            updates = plane_sync.compute_updates([PHASE3_LINE], self._profile())
        self.assertEqual(updates, [])

    def test_already_matching_marker_no_change(self):
        completed_line = PHASE3_LINE.replace("[BLOCKED:P3:external]", "[x]")
        with self._patch_state("completed"):
            updates = plane_sync.compute_updates([completed_line], self._profile())
        self.assertEqual(updates, [])

    def test_state_group_resolved_once_per_state_id(self):
        """Multiple issues sharing the same state UUID must only trigger one
        states/{id}/ lookup -- projects have a small fixed state set, so
        resolving it per-issue would be a wasteful N+1 API-call pattern."""
        second_line = PHASE3_LINE.replace(
            "22222222-2222-2222-2222-222222222222",
            "66666666-6666-6666-6666-666666666666",
        )
        calls = []

        def fake_fetch_state_group(*args, **kwargs):
            calls.append(args)
            return {"group": "completed"}

        with patch.multiple(
            plane_sync,
            fetch_issue_state=lambda *a, **kw: {"state": self.STATE_ID},
            fetch_state_group=fake_fetch_state_group,
        ):
            updates = plane_sync.compute_updates([PHASE3_LINE, second_line], self._profile())
        self.assertEqual(len(updates), 2)
        self.assertEqual(len(calls), 1, "state group should be resolved once and cached")


class TestSyncChecklistWithPlane(unittest.TestCase):
    def _profile(self):
        return {
            "workspace_name": "myworkspace",
            "plane_host": "https://plane.example.com",
            "plane_token": "tok",
            "plane_token_env": "PLANE_TOKEN",
        }

    def test_concurrent_edit_aborts_without_writing(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "fix_plan.md"
            path.write_text(PHASE3_LINE + "\n", encoding="utf-8")

            def fetch_and_mutate(*args, **kwargs):
                # Simulate another process editing the tracker mid-sync
                # (between the initial read and the final write).
                path.write_text(
                    path.read_text(encoding="utf-8") + "- [ ] concurrent edit\n",
                    encoding="utf-8",
                )
                return {"state": "55555555-5555-5555-5555-555555555555"}

            with patch.multiple(
                plane_sync,
                fetch_issue_state=fetch_and_mutate,
                fetch_state_group=lambda *a, **kw: {"group": "completed"},
            ):
                plane_sync.sync_checklist_with_plane(path, self._profile())

            content = path.read_text(encoding="utf-8")
            # Sync aborted before applying its update — original marker untouched.
            self.assertIn("[BLOCKED:P3:external]", content)
            # Concurrent edit preserved, not clobbered by a stale-snapshot write.
            self.assertIn("concurrent edit", content)
            # No leftover temp file from the atomic-write attempt.
            self.assertFalse((Path(d) / "fix_plan.md.tmp").exists())

    def test_write_succeeds_atomically_no_tmp_file_left(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "fix_plan.md"
            path.write_text(PHASE3_LINE + "\n", encoding="utf-8")

            with patch.multiple(
                plane_sync,
                fetch_issue_state=lambda *a, **kw: {"state": "55555555-5555-5555-5555-555555555555"},
                fetch_state_group=lambda *a, **kw: {"group": "completed"},
            ):
                plane_sync.sync_checklist_with_plane(path, self._profile())

            content = path.read_text(encoding="utf-8")
            self.assertIn("[x]", content)
            self.assertFalse((Path(d) / "fix_plan.md.tmp").exists())


class TestAutoDetectTrackerRoot(unittest.TestCase):
    """Issue #262: the __main__ fallback (no --fix-plan passed) must resolve
    .agents/fix_plan.md, not just .ralph/fix_plan.md."""

    def test_agents_only_workspace_auto_detected(self):
        with tempfile.TemporaryDirectory() as d:
            agents_dir = Path(d) / ".agents"
            agents_dir.mkdir()
            fix_plan = agents_dir / "fix_plan.md"
            fix_plan.write_text("# Fix Plan\n", encoding="utf-8")

            import subprocess
            # No --fix-plan: must auto-detect via cwd. No .ralph/ dir exists
            # here — pre-fix behavior hardcoded .ralph/fix_plan.md, so the
            # module would report "Target fix_plan file <cwd>/.ralph/fix_plan.md
            # not found" instead of finding the real file under .agents/.
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "plane_sync.py")],
                capture_output=True, text=True, cwd=d,
            )
            combined = result.stdout + result.stderr
            self.assertNotIn(".ralph", combined)
            self.assertNotIn("not found", combined)


if __name__ == "__main__":
    unittest.main()
