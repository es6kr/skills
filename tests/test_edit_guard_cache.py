#!/usr/bin/env python3
"""
Test check_plugin_cache_edit in edit-guard.sh
"""

import sys
import os
import json
import subprocess
import unittest

class TestEditGuardCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.guard_path = os.path.join(repo_root, "skills", "hook-kit", "resources", "edit-guard.sh")

    def run_guard(self, payload):
        proc = subprocess.run(
            ["bash", self.guard_path],
            input=json.dumps(payload),
            text=True,
            capture_output=True
        )
        return proc.returncode, proc.stdout, proc.stderr

    def test_block_cache_edit(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/home/dgs/.claude/plugins/cache/es6kr-skills/es6kr/0.1.0/skills/fix/SKILL.md",
                "new_string": "some modifications"
            }
        }
        rc, out, err = self.run_guard(payload)
        self.assertEqual(rc, 2)
        self.assertIn("DENIED: editing a non-canonical plugin cache file is prohibited", err)
        self.assertIn("/.claude/plugins/marketplaces/es6kr-skills/", err)

    def test_allow_cache_edit_with_override(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/home/dgs/.claude/plugins/cache/es6kr-skills/es6kr/0.1.0/skills/fix/SKILL.md",
                "new_string": "some modifications intentional-cache-edit"
            }
        }
        rc, out, err = self.run_guard(payload)
        self.assertEqual(rc, 0)

    def test_allow_canonical_marketplace_edit(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/home/dgs/.claude/plugins/marketplaces/es6kr-skills/skills/fix/SKILL.md",
                "new_string": "some modifications"
            }
        }
        rc, out, err = self.run_guard(payload)
        # Should not be blocked by cache guard
        self.assertNotIn("non-canonical plugin cache", err)

if __name__ == "__main__":
    unittest.main()
