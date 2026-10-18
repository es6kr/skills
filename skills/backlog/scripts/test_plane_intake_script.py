#!/usr/bin/env python3
"""Unit tests for skills/backlog/scripts/intake.py endpoint safety and issue detection."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

import intake


class TestIntakeScript(unittest.TestCase):
    def test_is_placeholder_endpoint(self):
        self.assertTrue(intake.is_placeholder_endpoint("", ""))
        self.assertTrue(intake.is_placeholder_endpoint("https://plane.example.com", ""))
        self.assertTrue(intake.is_placeholder_endpoint("https://plane.example.com", "https://plane.example.com/api/v1/workspaces/default"))
        self.assertTrue(intake.is_placeholder_endpoint("https://plane.internal", "https://plane.example.invalid/api/v1/workspaces/default"))
        self.assertFalse(intake.is_placeholder_endpoint("https://plane.dgs.ai.kr", "https://plane.dgs.ai.kr/api/v1/workspaces/dgs"))

    def test_parse_untracked_items_does_not_skip_github_issues(self):
        content = """## Priority Tasks
- [ ] Implement new endpoint auth (ref: https://github.com/es6kr/skills/issues/123)
- [ ] [INFRA-42] Existing Plane issue tracked
- [ ] Task linked to Plane browse https://plane.dgs.ai.kr/dgs/browse/DTWEB-10
- [ ] Task linked to Plane API https://plane.dgs.ai.kr/api/v1/workspaces/dgs/projects/123/issues/456
"""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
            tf.write(content)
            temp_path = tf.name

        try:
            items = intake.parse_untracked_items(temp_path)
            self.assertEqual(len(items), 1)
            self.assertIn("github.com/es6kr/skills/issues/123", items[0]["raw_line"])
            self.assertEqual(items[0]["title"], "Implement new endpoint auth")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
