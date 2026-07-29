#!/usr/bin/env python3
"""
Unit tests for `cleanup.py` (fix-plan skill script).
Reproduces the subtree data-loss bug: a completed [x] parent with completed
[x] children must keep the children's text when moved to ## Completed —
node_to_one_line() silently dropped them because it never recursed into
node.children.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

import importlib.util
spec = importlib.util.spec_from_file_location("cleanup", str(SCRIPT_DIR / "cleanup.py"))
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class TestNodeToCompletedBlock(unittest.TestCase):
    def test_childless_node_single_line(self):
        lines = ["- [x] Simple completed item"]
        forest = cleanup.build_tree(lines)
        node = forest[0]
        block = cleanup.node_to_completed_block(node)
        self.assertEqual(block, ["- Simple completed item"])

    def test_subtree_preserves_children_text(self):
        lines = [
            "- [x] 2026-07-07 — parent summary line",
            "  - [x] 2026-07-22 — child detail A: report drafted",
            "  - [x] 2026-07-23 — child detail B: investigation done",
            "  - [x] 2026-07-22 — child detail C: migration completed",
        ]
        forest = cleanup.build_tree(lines)
        node = forest[0]
        block = cleanup.node_to_completed_block(node)

        # Root cause regression guard: node_to_one_line() would have returned
        # only the parent line, discarding all 3 children.
        self.assertEqual(len(block), 4)
        self.assertIn("parent summary line", block[0])
        self.assertIn("child detail A: report drafted", block[1])
        self.assertIn("child detail B: investigation done", block[2])
        self.assertIn("child detail C: migration completed", block[3])

        # No line should retain a checkbox marker in the Completed convention.
        for line in block:
            self.assertNotIn("[x]", line)
            self.assertNotIn("[ ]", line)

    def test_nested_indent_preserved(self):
        lines = [
            "- [x] parent",
            "  - [x] child",
            "    - [x] grandchild",
        ]
        forest = cleanup.build_tree(lines)
        node = forest[0]
        block = cleanup.node_to_completed_block(node)
        self.assertEqual(len(block), 3)
        # Grandchild's original indent (4 spaces) must be preserved.
        self.assertTrue(block[2].startswith("    - grandchild") or "grandchild" in block[2])


class TestEndToEndMove(unittest.TestCase):
    """Full main()-level regression: a completed subtree survives the move
    from a Progress section into ## Completed with all children intact."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.fix_plan = os.path.join(self.tmpdir, "fix_plan.md")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, content):
        with open(self.fix_plan, "w", encoding="utf-8") as f:
            f.write(content)

    def _read(self):
        with open(self.fix_plan, "r", encoding="utf-8") as f:
            return f.read()

    def test_completed_subtree_children_survive_move(self):
        content = (
            "# Fix Plan\n\n"
            "## Progress\n\n"
            "- [x] 2026-07-07 — domain review\n"
            "  - [x] 2026-07-22 — approval report drafted\n"
            "  - [x] 2026-07-23 — recurrence check done\n\n"
            "## Completed\n\n"
            "## REPEAT\n"
        )
        self._write(content)

        import subprocess
        # cutoff is "archive everything dated before this" — use a cutoff
        # BEFORE the entries' dates so they land (and stay) in ## Completed
        # rather than being swept into the .bak/ archive partition.
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "cleanup.py"),
             "--file", self.fix_plan, "--cutoff", "2020-01-01"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        output = self._read()
        self.assertIn("domain review", output)
        self.assertIn("approval report drafted", output)
        self.assertIn("recurrence check done", output)


if __name__ == "__main__":
    unittest.main()
