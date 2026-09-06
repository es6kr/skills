#!/usr/bin/env python3
"""
Unit tests for `claim_item.py` (fix-plan skill script).

`claim.md` documents the `[CLAIMED:<sid>:<ts>]` lease-tag convention, but the
skill's `scripts/` directory had no sanctioned way to stamp/refresh/release
that tag -- `add_item.py` only appends new items, and
`block-direct-checklist-edit.js` blocks direct Edit/Write on the tracker.
This module closes that gap the same way `add_item.py` closed the "add" gap.
"""

import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

import importlib.util
spec = importlib.util.spec_from_file_location("claim_item", str(SCRIPT_DIR / "claim_item.py"))
claim_item = importlib.util.module_from_spec(spec)
spec.loader.exec_module(claim_item)


NOW = "2026-08-26T12:34"
STALE_TTL_HOURS = 4


def write_tracker(d, body):
    path = Path(d) / "fix_plan.md"
    path.write_text(body, encoding="utf-8")
    return path


class TestClaimNewItem(unittest.TestCase):
    def test_stamps_claim_on_open_marker(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [ ] do the thing\n  - **Why**: because\n")
            result = claim_item.claim(path, action="do the thing", sid="c305a3d5", now=NOW)
            self.assertTrue(result["ok"])
            content = path.read_text(encoding="utf-8")
            self.assertIn("- [ ] [CLAIMED:c305a3d5:2026-08-26T12:34] do the thing", content)

    def test_stamps_claim_on_blocked_selfable_marker(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [BLOCKED:P0:selfable] do the thing\n")
            result = claim_item.claim(path, action="do the thing", sid="c305a3d5", now=NOW)
            self.assertTrue(result["ok"])
            content = path.read_text(encoding="utf-8")
            self.assertIn(
                "- [BLOCKED:P0:selfable] [CLAIMED:c305a3d5:2026-08-26T12:34] do the thing",
                content,
            )

    def test_rejects_blocked_external(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [BLOCKED:P0:external] do the thing\n")
            result = claim_item.claim(path, action="do the thing", sid="c305a3d5", now=NOW)
            self.assertFalse(result["ok"])
            self.assertIn("external", result["error"])
            # File must be untouched on rejection.
            self.assertEqual(path.read_text(encoding="utf-8"), "- [BLOCKED:P0:external] do the thing\n")

    def test_rejects_completed_marker(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [x] do the thing\n")
            result = claim_item.claim(path, action="do the thing", sid="c305a3d5", now=NOW)
            self.assertFalse(result["ok"])

    def test_action_not_found_errors(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [ ] a different thing\n")
            result = claim_item.claim(path, action="do the thing", sid="c305a3d5", now=NOW)
            self.assertFalse(result["ok"])
            self.assertIn("not found", result["error"])

    def test_atomic_write_no_tmp_file_left(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [ ] do the thing\n")
            claim_item.claim(path, action="do the thing", sid="c305a3d5", now=NOW)
            # _write_lines uses tempfile.mkstemp(prefix=".claim_item.", suffix=".tmp"),
            # so asserting on "fix_plan.md.tmp" passed vacuously -- that name is
            # never produced. Assert on the real leak shape instead.
            leftovers = list(Path(d).glob(".claim_item.*"))
            self.assertEqual(leftovers, [], f"temp file leaked: {leftovers}")


class TestClaimExistingTag(unittest.TestCase):
    def test_own_claim_refreshes_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(
                d, "- [ ] [CLAIMED:c305a3d5:2026-08-26T08:00] do the thing\n"
            )
            result = claim_item.claim(path, action="do the thing", sid="c305a3d5", now=NOW)
            self.assertTrue(result["ok"])
            content = path.read_text(encoding="utf-8")
            self.assertIn("[CLAIMED:c305a3d5:2026-08-26T12:34]", content)
            self.assertNotIn("08:00", content)

    def test_fresh_other_session_claim_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            original = "- [ ] [CLAIMED:deadbeef:2026-08-26T10:00] do the thing\n"
            path = write_tracker(d, original)
            # 2.5h after the other session's stamp -- within the 4h TTL.
            result = claim_item.claim(
                path, action="do the thing", sid="c305a3d5", now="2026-08-26T12:30",
                ttl_hours=STALE_TTL_HOURS,
            )
            self.assertFalse(result["ok"])
            self.assertIn("in flight", result["error"])
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_stale_other_session_claim_takeover(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(
                d, "- [ ] [CLAIMED:deadbeef:2026-08-26T06:00] do the thing\n"
            )
            # 6.5h after the other session's stamp -- past the 4h TTL.
            result = claim_item.claim(
                path, action="do the thing", sid="c305a3d5", now="2026-08-26T12:30",
                ttl_hours=STALE_TTL_HOURS,
            )
            self.assertTrue(result["ok"])
            content = path.read_text(encoding="utf-8")
            self.assertIn("[CLAIMED:c305a3d5:2026-08-26T12:30]", content)
            self.assertNotIn("deadbeef", content)

    def test_idempotent_reclaim_does_not_duplicate_tag(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(
                d, "- [ ] [CLAIMED:c305a3d5:2026-08-26T12:00] do the thing\n"
            )
            claim_item.claim(path, action="do the thing", sid="c305a3d5", now=NOW)
            content = path.read_text(encoding="utf-8")
            self.assertEqual(content.count("[CLAIMED:"), 1)


class TestRelease(unittest.TestCase):
    def test_release_removes_claim_tag(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(
                d, "- [ ] [CLAIMED:c305a3d5:2026-08-26T12:00] do the thing\n"
            )
            result = claim_item.release(path, action="do the thing", sid="c305a3d5")
            self.assertTrue(result["ok"])
            content = path.read_text(encoding="utf-8")
            self.assertEqual(content, "- [ ] do the thing\n")

    def test_release_no_op_when_unclaimed(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [ ] do the thing\n")
            result = claim_item.release(path, action="do the thing", sid="c305a3d5")
            self.assertTrue(result["ok"])
            self.assertEqual(path.read_text(encoding="utf-8"), "- [ ] do the thing\n")

    def test_release_rejects_other_sessions_claim(self):
        with tempfile.TemporaryDirectory() as d:
            original = "- [ ] [CLAIMED:deadbeef:2026-08-26T12:00] do the thing\n"
            path = write_tracker(d, original)
            result = claim_item.release(path, action="do the thing", sid="c305a3d5")
            self.assertFalse(result["ok"])
            self.assertEqual(path.read_text(encoding="utf-8"), original)


class TestPlaneSyncWiring(unittest.TestCase):
    """Companion to plane_sync.transition_issue_to_started(): claiming an
    item that is also a Plane index line (`[IDENT-N] title -> Plane (url)`)
    should push the claim through to the linked Plane issue's status --
    otherwise the [CLAIMED] tag only ever reflects locally."""

    PLANE_ACTION = (
        "[INFRA-6] title -> Plane (https://plane.example.com/myworkspace/"
        "projects/11111111-1111-1111-1111-111111111111/issues/"
        "22222222-2222-2222-2222-222222222222)"
    )

    def _plane_profile(self):
        return {"plane_host": "https://plane.example.com", "plane_token": "tok"}

    def test_claim_with_plane_index_line_triggers_started_transition(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, f"- [ ] {self.PLANE_ACTION}\n")
            calls = []

            def fake_transition(profile, workspace, project, issue):
                calls.append((workspace, project, issue))
                return {"id": "issue1"}

            with unittest.mock.patch(
                "plane_sync.transition_issue_to_started", side_effect=fake_transition
            ):
                result = claim_item.claim(
                    path, action=self.PLANE_ACTION, sid="c305a3d5", now=NOW,
                    plane_profile=self._plane_profile(),
                )
            self.assertTrue(result["ok"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0], ("myworkspace", "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"))
            self.assertTrue(result["plane_sync"]["ok"])

    def test_claim_without_plane_profile_skips_plane_sync(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, f"- [ ] {self.PLANE_ACTION}\n")
            with unittest.mock.patch("plane_sync.transition_issue_to_started") as mock_fn:
                result = claim_item.claim(path, action=self.PLANE_ACTION, sid="c305a3d5", now=NOW)
            mock_fn.assert_not_called()
            self.assertTrue(result["ok"])
            self.assertNotIn("plane_sync", result)

    def test_claim_non_plane_line_skips_plane_sync(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [ ] do the thing\n")
            with unittest.mock.patch("plane_sync.transition_issue_to_started") as mock_fn:
                result = claim_item.claim(
                    path, action="do the thing", sid="c305a3d5", now=NOW,
                    plane_profile=self._plane_profile(),
                )
            mock_fn.assert_not_called()
            self.assertTrue(result["ok"])
            self.assertNotIn("plane_sync", result)

    def test_plane_sync_failure_does_not_fail_claim(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, f"- [ ] {self.PLANE_ACTION}\n")
            with unittest.mock.patch(
                "plane_sync.transition_issue_to_started",
                return_value={"error": "no started-group state"},
            ):
                result = claim_item.claim(
                    path, action=self.PLANE_ACTION, sid="c305a3d5", now=NOW,
                    plane_profile=self._plane_profile(),
                )
            # Local claim already succeeded (atomic write happens first) --
            # a Plane-side failure is surfaced, not treated as a claim failure.
            self.assertTrue(result["ok"])
            self.assertFalse(result["plane_sync"]["ok"])
            content = path.read_text(encoding="utf-8")
            self.assertIn("[CLAIMED:c305a3d5:2026-08-26T12:34]", content)


class TestStaleness(unittest.TestCase):
    def test_is_stale_true_past_ttl(self):
        self.assertTrue(
            claim_item.is_stale("2026-08-26T06:00", now="2026-08-26T12:30", ttl_hours=4)
        )

    def test_is_stale_false_within_ttl(self):
        self.assertFalse(
            claim_item.is_stale("2026-08-26T10:00", now="2026-08-26T12:30", ttl_hours=4)
        )


# --- Review-feedback regression tests (PR #451 consolidate) -----------------
# Each class below pins a finding raised in the AI Review Summary for PR #451.


class TestInputValidation(unittest.TestCase):
    """Rows 2 and 6: lease inputs must be validated before the tracker is written."""

    def test_rejects_non_hex_sid_without_touching_tracker(self):
        # A non-hex sid parses fine on write but ITEM_RE can never match the
        # resulting tag, which strands the item permanently.
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [ ] do the thing\n")
            before = path.read_text(encoding="utf-8")
            result = claim_item.claim(path, action="do the thing", sid="ZZZZZZZZ", now=NOW)
            self.assertFalse(result["ok"])
            self.assertIn("sid", result["error"])
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_rejects_non_positive_ttl(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [ ] task b\n")
            result = claim_item.claim(
                path, action="task b", sid="aaaaaaaa", now=NOW, ttl_hours=0
            )
            self.assertFalse(result["ok"])
            self.assertIn("ttl", result["error"].lower())

    def test_rejects_malformed_now(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [ ] task c\n")
            result = claim_item.claim(path, action="task c", sid="aaaaaaaa", now="garbage")
            self.assertFalse(result["ok"])
            self.assertIn("now", result["error"].lower())

    def test_corrupt_stored_timestamp_returns_structured_error(self):
        # Must not raise ValueError out of claim() -- the documented contract
        # is a {ok: False, error: ...} result.
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [ ] [CLAIMED:aaaaaaaa:garbage] task d\n")
            result = claim_item.claim(path, action="task d", sid="bbbbbbbb", now=NOW)
            self.assertFalse(result["ok"])
            self.assertIn("timestamp", result["error"].lower())

    def test_release_rejects_invalid_sid(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [ ] [CLAIMED:aaaaaaaa:2026-08-26T10:00] task e\n")
            result = claim_item.release(path, action="task e", sid="NOTHEX!!")
            self.assertFalse(result["ok"])
            self.assertIn("sid", result["error"])


class TestDuplicateActionText(unittest.TestCase):
    """Row 8: _find_item silently targeting the first match misroutes the lease."""

    def test_ambiguous_claimable_duplicates_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [ ] add tests\n- [ ] add tests\n")
            before = path.read_text(encoding="utf-8")
            result = claim_item.claim(path, action="add tests", sid="aaaaaaaa", now=NOW)
            self.assertFalse(result["ok"])
            self.assertIn("ambiguous", result["error"].lower())
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_completed_duplicate_does_not_mask_claimable_line(self):
        # An [x] copy appearing first must not produce a "cannot claim [x]"
        # rejection while an open copy exists further down.
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, "- [x] add tests\n- [ ] add tests\n")
            result = claim_item.claim(path, action="add tests", sid="aaaaaaaa", now=NOW)
            self.assertTrue(result["ok"], msg=result.get("error"))
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "- [x] add tests")
            self.assertIn("[CLAIMED:aaaaaaaa:", lines[1])


class TestPlaneSyncExceptionBoundary(unittest.TestCase):
    """Row 4: an exception from the Plane push must not escape after the local write."""

    PLANE_ACTION = (
        "[INFRA-6] title -> Plane (https://plane.example.com/myworkspace/"
        "projects/11111111-1111-1111-1111-111111111111/issues/"
        "22222222-2222-2222-2222-222222222222)"
    )

    def test_plane_exception_is_captured_and_local_claim_survives(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, f"- [ ] {self.PLANE_ACTION}\n")
            with unittest.mock.patch(
                "plane_sync.transition_issue_to_started",
                side_effect=KeyError("plane_token_env"),
            ):
                result = claim_item.claim(
                    path, action=self.PLANE_ACTION, sid="c305a3d5", now=NOW,
                    plane_profile={"plane_host": "https://plane.example.com"},
                )
            self.assertTrue(result["ok"])
            self.assertFalse(result["plane_sync"]["ok"])
            self.assertIn("[CLAIMED:c305a3d5:", path.read_text(encoding="utf-8"))


class TestPlaneSyncCliBranch(unittest.TestCase):
    """Row 9: the --plane-sync CLI branch is the only production entry and was untested."""

    PLANE_ACTION = TestPlaneSyncExceptionBoundary.PLANE_ACTION

    def test_cli_plane_sync_threads_profile_through(self):
        import workspace_profile

        with tempfile.TemporaryDirectory() as d:
            path = write_tracker(d, f"- [ ] {self.PLANE_ACTION}\n")
            argv = [
                "claim_item.py", "claim", "--file", str(path),
                "--action", self.PLANE_ACTION, "--sid", "c305a3d5",
                "--now", NOW, "--plane-sync",
            ]
            profile = {"plane_host": "https://plane.example.com", "plane_token": "tok"}
            seen = {}

            def fake_transition(prof, workspace, project, issue):
                seen["profile"] = prof
                return {"id": "issue1"}

            with unittest.mock.patch.object(sys, "argv", argv), \
                    unittest.mock.patch.object(
                        workspace_profile, "get_profile", return_value=profile), \
                    unittest.mock.patch(
                        "plane_sync.transition_issue_to_started",
                        side_effect=fake_transition):
                rc = claim_item.main()

            self.assertEqual(rc, 0)
            self.assertEqual(seen.get("profile"), profile)


if __name__ == "__main__":
    unittest.main()
