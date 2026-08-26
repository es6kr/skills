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
            self.assertFalse((Path(d) / "fix_plan.md.tmp").exists())


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


class TestStaleness(unittest.TestCase):
    def test_is_stale_true_past_ttl(self):
        self.assertTrue(
            claim_item.is_stale("2026-08-26T06:00", now="2026-08-26T12:30", ttl_hours=4)
        )

    def test_is_stale_false_within_ttl(self):
        self.assertFalse(
            claim_item.is_stale("2026-08-26T10:00", now="2026-08-26T12:30", ttl_hours=4)
        )


if __name__ == "__main__":
    unittest.main()
