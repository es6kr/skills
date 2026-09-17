#!/usr/bin/env python3
"""
Unit tests for prune_merged_worktrees.py
"""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import prune_merged_worktrees as pmw


class TestPruneMergedWorktrees(unittest.TestCase):

    def test_get_worktrees_parsing(self):
        sample_porcelain = (
            "worktree /path/to/main\n"
            "HEAD 1111111111111111111111111111111111111111\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /path/to/worktree1\n"
            "HEAD 2222222222222222222222222222222222222222\n"
            "branch refs/heads/feat-branch\n"
            "\n"
            "worktree /path/to/worktree2\n"
            "HEAD 3333333333333333333333333333333333333333\n"
            "detached\n"
        )

        with patch("prune_merged_worktrees.run_git") as mock_run_git:
            mock_run_git.return_value = (0, sample_porcelain, "")
            worktrees = pmw.get_worktrees(Path("/path/to/main"))

            self.assertEqual(len(worktrees), 3)
            self.assertTrue(worktrees[0].is_main)
            self.assertEqual(worktrees[0].branch, "main")

            self.assertFalse(worktrees[1].is_main)
            self.assertEqual(worktrees[1].branch, "feat-branch")
            self.assertEqual(worktrees[1].head_sha, "2222222222222222222222222222222222222222")

            self.assertFalse(worktrees[2].is_main)
            self.assertIsNone(worktrees[2].branch)

    def test_check_clean(self):
        with patch("prune_merged_worktrees.run_git") as mock_run_git:
            # Clean
            mock_run_git.return_value = (0, "", "")
            self.assertTrue(pmw.check_clean(Path("/fake/wt")))

            # Dirty
            mock_run_git.return_value = (0, " M modified.txt", "")
            self.assertFalse(pmw.check_clean(Path("/fake/wt")))

    def test_check_mid_operation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            gitdir = temp_path / ".git"
            gitdir.mkdir()

            with patch("prune_merged_worktrees.run_git") as mock_run_git:
                # No operation
                mock_run_git.side_effect = [
                    (0, str(gitdir), ""),
                    (0, "", "")
                ]
                mid_op, _ = pmw.check_mid_operation(temp_path)
                self.assertFalse(mid_op)

                # Rebase in progress
                (gitdir / "REBASE_HEAD").touch()
                mock_run_git.side_effect = [
                    (0, str(gitdir), ""),
                    (0, "", "")
                ]
                mid_op, reason = pmw.check_mid_operation(temp_path)
                self.assertTrue(mid_op)
                self.assertIn("REBASE_HEAD", reason)

    def test_format_table_output(self):
        wt1 = pmw.WorktreeInfo(Path("repo/.worktrees/branch-a"), "1234567890abcdef", "branch-a")
        report1 = pmw.WorktreeReport(wt1, "es6kr/skills")
        report1.is_clean = True
        report1.is_merged = True
        report1.pr_number = 484
        report1.pr_url = "https://github.com/es6kr/skills/pull/484"
        report1.pr_head_sha = "1234567890abcdef"
        report1.action = "Pruned"

        wt2 = pmw.WorktreeInfo(Path("repo/.worktrees/branch-b"), "abcdef1234567890", "branch-b")
        report2 = pmw.WorktreeReport(wt2, "es6kr/skills")
        report2.is_clean = False
        report2.action = "Skipped"
        report2.skip_reason = "dirty working tree"

        table = pmw.format_table([report1, report2], execute=True)

        # Verify strict user constraints:
        # 1. Combined repository + PR link column
        self.assertIn("[skills/pull/484](https://github.com/es6kr/skills/pull/484)", table)
        # 2. Combined Local / Remote SHA column
        self.assertIn("`12345678` / `12345678` (match)", table)
        # 3. No separate bare URLs or footnote citations
        self.assertNotIn("\n[1]:", table)
        self.assertNotIn("https://github.com/es6kr/skills/pull/484 |", table)  # URL not bare in its own column


if __name__ == "__main__":
    unittest.main()
