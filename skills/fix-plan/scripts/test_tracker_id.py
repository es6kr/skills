#!/usr/bin/env python3
"""test_tracker_id.py — unit tests for fix-plan tracker ID uniqueness checker and sequence resolver."""

import os
import sys
import tempfile
import unittest

# Ensure skills/fix-plan/scripts is in import path
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import tracker_id


class TestTrackerId(unittest.TestCase):
    def setUp(self):
        self.tmp_fd, self.tmp_path = tempfile.mkstemp(suffix=".md", prefix="tracker_test_")
        os.close(self.tmp_fd)

    def tearDown(self):
        if os.path.exists(self.tmp_path):
            try:
                os.unlink(self.tmp_path)
            except OSError:
                pass

    def test_scan_used_sequences_empty_file(self):
        with open(self.tmp_path, "w", encoding="utf-8") as f:
            f.write("# Empty Tracker\n\n## Progress\n")
        used = tracker_id.scan_used_sequences(self.tmp_path, "AIAUTO")
        self.assertEqual(used, set())

    def test_scan_used_sequences_multiple_prefixes(self):
        content = (
            "# Tracker\n\n"
            "## Progress\n"
            "- [ ] [AIAUTO-1] first item\n"
            "- [x] [AIAUTO-2] second item\n"
            "- [BLOCKED:P2:selfable] [AIAUTO-5] fifth item\n"
            "- [ ] [INFRA-1] infra item\n"
            "- [ ] [AIAUTO-03] padded sequence\n"
        )
        with open(self.tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        used_aiauto = tracker_id.scan_used_sequences(self.tmp_path, "AIAUTO")
        self.assertEqual(used_aiauto, {1, 2, 3, 5})

        used_infra = tracker_id.scan_used_sequences(self.tmp_path, "INFRA")
        self.assertEqual(used_infra, {1})

    def test_get_next_available_id_no_collision_requested(self):
        content = (
            "- [ ] [AIAUTO-1] item 1\n"
            "- [ ] [AIAUTO-2] item 2\n"
        )
        with open(self.tmp_path, "w", encoding="utf-8") as f:
            f.write(content)

        assigned_id, collided = tracker_id.get_next_available_id(self.tmp_path, "AIAUTO", requested_seq=3)
        self.assertEqual(assigned_id, "AIAUTO-3")
        self.assertFalse(collided)

    def test_get_next_available_id_with_collision_increments(self):
        content = (
            "- [ ] [AIAUTO-1] item 1\n"
            "- [ ] [AIAUTO-2] item 2\n"
            "- [ ] [AIAUTO-3] item 3\n"
        )
        with open(self.tmp_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Requesting AIAUTO-2 which is already in use
        assigned_id, collided = tracker_id.get_next_available_id(self.tmp_path, "AIAUTO", requested_seq=2)
        self.assertEqual(assigned_id, "AIAUTO-4")
        self.assertTrue(collided)

    def test_get_next_available_id_unspecified_requested_seq(self):
        content = (
            "- [ ] [AIAUTO-10] item 10\n"
            "- [ ] [AIAUTO-20] item 20\n"
        )
        with open(self.tmp_path, "w", encoding="utf-8") as f:
            f.write(content)

        # When no requested_seq is provided, default to max + 1
        assigned_id, collided = tracker_id.get_next_available_id(self.tmp_path, "AIAUTO")
        self.assertEqual(assigned_id, "AIAUTO-21")
        self.assertFalse(collided)

    def test_get_next_available_id_fills_or_skips_gaps(self):
        content = (
            "- [ ] [AIAUTO-1] item 1\n"
            "- [ ] [AIAUTO-3] item 3\n"
        )
        with open(self.tmp_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Requesting seq 1 should increment to next available (which is 2)
        assigned_id, collided = tracker_id.get_next_available_id(self.tmp_path, "AIAUTO", requested_seq=1)
        self.assertEqual(assigned_id, "AIAUTO-2")
        self.assertTrue(collided)


if __name__ == "__main__":
    unittest.main()
