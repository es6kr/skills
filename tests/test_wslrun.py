#!/usr/bin/env python3
"""
Unit tests for scripts/wslrun.py
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add scripts directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import wslrun

class TestWslrunPathTranslation(unittest.TestCase):
    def test_win_to_wsl_path_standard(self):
        self.assertEqual(
            wslrun.win_to_wsl_path(r"C:\Users\DAEGUNSOFT\ghq\github.com\es6kr"),
            "/mnt/c/Users/DAEGUNSOFT/ghq/github.com/es6kr"
        )

    def test_win_to_wsl_path_forward_slash(self):
        self.assertEqual(
            wslrun.win_to_wsl_path("D:/projects/skills/scripts/test.py"),
            "/mnt/d/projects/skills/scripts/test.py"
        )

    def test_win_to_wsl_path_bare_drive(self):
        self.assertEqual(wslrun.win_to_wsl_path("C:"), "/mnt/c")
        self.assertEqual(wslrun.win_to_wsl_path("c:"), "/mnt/c")

    def test_win_to_wsl_path_already_posix(self):
        self.assertEqual(wslrun.win_to_wsl_path("/mnt/c/foo/bar"), "/mnt/c/foo/bar")
        self.assertEqual(wslrun.win_to_wsl_path("/home/dgs/work"), "/home/dgs/work")

    def test_win_to_wsl_path_empty(self):
        self.assertEqual(wslrun.win_to_wsl_path(""), "")

class TestWslrunArgTranslation(unittest.TestCase):
    def test_translate_arg_absolute_win_path(self):
        self.assertEqual(
            wslrun.translate_arg(r"C:\Users\DAEGUNSOFT\.agents\fix_plan.md"),
            "/mnt/c/Users/DAEGUNSOFT/.agents/fix_plan.md"
        )

    def test_translate_arg_flag_with_win_path(self):
        self.assertEqual(
            wslrun.translate_arg(r"--file=C:\Users\DAEGUNSOFT\.agents\fix_plan.md"),
            "--file=/mnt/c/Users/DAEGUNSOFT/.agents/fix_plan.md"
        )

    def test_translate_arg_preserves_non_path(self):
        self.assertEqual(
            wslrun.translate_arg("--match=[CLAIMED:eec8133a]"),
            "--match=[CLAIMED:eec8133a]"
        )
        self.assertEqual(
            wslrun.translate_arg("--summary=fix: resolve [x] issue"),
            "--summary=fix: resolve [x] issue"
        )
        self.assertEqual(
            wslrun.translate_arg("-v"),
            "-v"
        )

    def test_translate_arg_existing_file(self):
        # Current file definitely exists
        this_file = os.path.abspath(__file__)
        expected_wsl = wslrun.win_to_wsl_path(this_file)
        # Passing relative path from repo root
        rel_path = os.path.relpath(this_file, os.getcwd())
        if sys.platform == "win32":
            self.assertEqual(wslrun.translate_arg(rel_path), expected_wsl)

class TestWslrunCliParsing(unittest.TestCase):
    def test_help_returns_zero(self):
        self.assertEqual(wslrun.main(["--help"]), 0)
        self.assertEqual(wslrun.main(["-h"]), 0)

    def test_empty_args_returns_one(self):
        self.assertEqual(wslrun.main([]), 1)

    @patch("subprocess.run")
    def test_basic_invocation(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        ret = wslrun.main(["scripts/verify-plugin-spec.py", "--flag"])
        self.assertEqual(ret, 0)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        if sys.platform == "win32":
            self.assertIn("wsl", cmd[0].lower())
            self.assertIn("python3", cmd)
        else:
            self.assertEqual(cmd[0], "python3")

    @patch("subprocess.run")
    def test_uv_flag_invocation(self, mock_run):
        mock_run.return_value = MagicMock(returncode=42)
        ret = wslrun.main(["--uv", "tests/test_deploy.py"])
        self.assertEqual(ret, 42)
        cmd = mock_run.call_args[0][0]
        self.assertIn("uv", cmd)
        self.assertIn("run", cmd)

    @patch("subprocess.run")
    def test_custom_python_bin(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        ret = wslrun.main(["--python", "python3.12", "script.py"])
        self.assertEqual(ret, 0)
        cmd = mock_run.call_args[0][0]
        self.assertIn("python3.12", cmd)

if __name__ == "__main__":
    unittest.main()
