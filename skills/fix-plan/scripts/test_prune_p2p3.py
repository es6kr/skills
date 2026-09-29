"""Behavioural tests for prune_p2p3.apply_prune.

The tracker file these scripts rewrite is edited concurrently by multiple sessions, and this
repo has already lost data once to a non-atomic write in a sibling tracker-mutating script.
`apply_prune` is the most dangerous caller of that pattern, because it is a *migration*: it
moves items out of the active sections into `## TODO`. If the write fails partway, the items
are gone rather than merely reformatted.

So the atomicity test here is not a style check — it pins the one property that decides
whether a failed run costs nothing or costs the tracker.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import prune_p2p3


TRACKER = """# Ralph Fix Plan

## Priority Tasks

- [ ] (P1) keep me — P1 is never pruned
- [ ] (P2) move me to TODO
- [ ] (P3) move me too

## Completed

- [x] already done
"""


class TestApplyPrune(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fix_plan.md"
        self.path.write_text(TRACKER, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_migrates_p2_p3_into_todo_and_leaves_p1(self):
        prune_p2p3.apply_prune(self.path, prune_all=True)
        out = self.path.read_text(encoding="utf-8")

        self.assertIn("## TODO", out, "a ## TODO section must exist after migration")
        self.assertIn("(P1) keep me", out, "P1 items must survive the prune")
        self.assertIn("(P2) move me to TODO", out)
        self.assertIn("(P3) move me too", out)

        # the moved items must no longer sit under ## Priority Tasks
        priority_block = out.split("## Priority Tasks", 1)[1].split("##", 1)[0]
        self.assertIn("(P1) keep me", priority_block)
        self.assertNotIn("(P2) move me to TODO", priority_block)
        self.assertNotIn("(P3) move me too", priority_block)

    def test_write_is_atomic_so_a_failed_write_leaves_the_tracker_intact(self):
        """A failure at the commit point must leave the ORIGINAL tracker byte-identical.

        With a temp-file + os.replace write, the original is untouched until the rename, so
        injecting a failure into os.replace loses nothing. With an in-place
        `Path.write_text`, the original has already been truncated by the time anything can
        fail — and this assertion catches exactly that difference.
        """
        original = self.path.read_text(encoding="utf-8")

        with mock.patch.object(prune_p2p3.os, "replace", side_effect=RuntimeError("injected")):
            with self.assertRaises(RuntimeError):
                prune_p2p3.apply_prune(self.path, prune_all=True)

        self.assertEqual(
            self.path.read_text(encoding="utf-8"),
            original,
            "a failed write must not modify the tracker at all",
        )

    def test_no_temp_files_are_left_behind_on_success(self):
        prune_p2p3.apply_prune(self.path, prune_all=True)
        leftovers = [p.name for p in self.path.parent.iterdir() if p.name != self.path.name]
        self.assertEqual(leftovers, [], f"temp files leaked into the tracker directory: {leftovers}")


if __name__ == "__main__":
    unittest.main()
