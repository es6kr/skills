#!/usr/bin/env python3
"""Unit tests for qdrant-dup-check.py.

No network, no fastembed dependency -- embed() and search() are patched at
the module level so the exit-code contract (0 = no signal/skip, 3 = hit) can
be pinned without a live Qdrant instance or the fastembed model download.
"""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

spec = importlib.util.spec_from_file_location("qdrant_dup_check", str(SCRIPT_DIR / "qdrant-dup-check.py"))
qdc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qdc)


class TestParseArgs(unittest.TestCase):
    def test_defaults(self):
        args = qdc.parse_args(["--text", "some title"])
        self.assertEqual(args.text, "some title")
        self.assertEqual(args.threshold, 0.85)
        self.assertEqual(args.limit, 3)

    def test_overrides(self):
        args = qdc.parse_args(
            [
                "--text",
                "some title",
                "--threshold",
                "0.7",
                "--collection",
                "claude-memory-dgs",
                "--qdrant-url",
                "http://100.82.193.45:30633",
                "--limit",
                "5",
            ]
        )
        self.assertEqual(args.threshold, 0.7)
        self.assertEqual(args.collection, "claude-memory-dgs")
        self.assertEqual(args.qdrant_url, "http://100.82.193.45:30633")
        self.assertEqual(args.limit, 5)


class TestMainExitCodes(unittest.TestCase):
    def _run(self, argv, hits):
        with patch.object(qdc, "embed", return_value=[0.0] * 384), patch.object(qdc, "search", return_value=hits):
            with self.assertRaises(SystemExit) as ctx:
                qdc.main(argv)
            return ctx.exception.code

    def test_no_hits_exits_0(self):
        code = self._run(["--text", "unrelated new topic"], hits=[])
        self.assertEqual(code, 0)

    def test_hits_below_threshold_exit_0(self):
        hits = [{"score": 0.62, "payload": {"document": "some other item"}}]
        code = self._run(["--text", "new item"], hits=hits)
        self.assertEqual(code, 0)

    def test_hit_at_threshold_exits_3(self):
        hits = [{"score": 0.85, "payload": {"document": "duplicate candidate"}}]
        code = self._run(["--text", "duplicate candidate again"], hits=hits)
        self.assertEqual(code, 3)

    def test_hit_above_threshold_exits_3(self):
        hits = [{"score": 0.93, "payload": {"document": "duplicate candidate", "metadata": {"issue_url": "https://plane.example/x"}}}]
        code = self._run(["--text", "duplicate candidate again"], hits=hits)
        self.assertEqual(code, 3)

    def test_custom_threshold_respected(self):
        hits = [{"score": 0.75, "payload": {"document": "borderline item"}}]
        code = self._run(["--text", "borderline item variant", "--threshold", "0.7"], hits=hits)
        self.assertEqual(code, 3)


class TestFailOpen(unittest.TestCase):
    def test_missing_fastembed_exits_0(self):
        with patch.object(qdc, "embed", side_effect=ImportError("no module named fastembed")):
            with self.assertRaises(SystemExit) as ctx:
                qdc.main(["--text", "anything"])
            self.assertEqual(ctx.exception.code, 0)

    def test_embedding_error_exits_0(self):
        with patch.object(qdc, "embed", side_effect=RuntimeError("model load failed")):
            with self.assertRaises(SystemExit) as ctx:
                qdc.main(["--text", "anything"])
            self.assertEqual(ctx.exception.code, 0)

    def test_qdrant_unreachable_exits_0(self):
        import urllib.error

        with patch.object(qdc, "embed", return_value=[0.0] * 384), patch.object(
            qdc, "search", side_effect=urllib.error.URLError("connection refused")
        ):
            with self.assertRaises(SystemExit) as ctx:
                qdc.main(["--text", "anything"])
            self.assertEqual(ctx.exception.code, 0)

    def test_search_generic_error_exits_0(self):
        with patch.object(qdc, "embed", return_value=[0.0] * 384), patch.object(
            qdc, "search", side_effect=RuntimeError("500 from qdrant")
        ):
            with self.assertRaises(SystemExit) as ctx:
                qdc.main(["--text", "anything"])
            self.assertEqual(ctx.exception.code, 0)


class TestRenderHit(unittest.TestCase):
    def test_includes_score_and_snippet(self):
        hit = {"score": 0.912, "payload": {"document": "a" * 200}}
        line = qdc.render_hit(hit)
        self.assertIn("0.912", line)
        self.assertEqual(len(line), len("  score=0.912  ") + 120)

    def test_includes_url_when_present(self):
        hit = {"score": 0.9, "payload": {"document": "x", "metadata": {"pr_url": "https://github.com/x/y/pull/1"}}}
        line = qdc.render_hit(hit)
        self.assertIn("https://github.com/x/y/pull/1", line)

    def test_no_url_key_omitted(self):
        hit = {"score": 0.9, "payload": {"document": "x"}}
        line = qdc.render_hit(hit)
        self.assertNotIn("(", line)


if __name__ == "__main__":
    unittest.main()
