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

    def test_process_repository_rejects_sha_mismatch_before_execute(self):
        """A worktree whose branch name matches an old merged PR, but whose local
        HEAD has diverged (new commits since that PR merged), must NOT be pruned
        via the GitHub path -- exact HEAD SHA must match the PR's headRefOid.
        Regression test for PR #539 review finding (data-loss risk on branch reuse)."""
        wt = pmw.WorktreeInfo(
            Path("/repo/.worktrees/reused-branch"),
            "deadbeef00000000000000000000000000000000",
            "reused-branch",
        )

        with patch("prune_merged_worktrees.get_worktrees", return_value=[wt]), \
             patch("prune_merged_worktrees.check_mid_operation", return_value=(False, "")), \
             patch("prune_merged_worktrees.check_clean", return_value=True), \
             patch("prune_merged_worktrees.get_origin_info", return_value=("git@github.com:es6kr/skills.git", "github", "es6kr/skills")), \
             patch("prune_merged_worktrees.get_default_upstream", return_value=None), \
             patch("prune_merged_worktrees.check_github_merged", return_value={
                 "number": 100,
                 "url": "https://github.com/es6kr/skills/pull/100",
                 "headRefOid": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # differs from wt.head_sha
             }), \
             patch("prune_merged_worktrees.run_git") as mock_run_git:
            mock_run_git.return_value = (0, "/repo", "")  # only the top-level rev-parse should fire
            reports = pmw.process_repository(Path("/repo"), execute=True, delete_branch=False)

        self.assertEqual(len(reports), 1)
        report = reports[0]
        self.assertFalse(report.is_merged, "SHA-mismatched branch must not be classified merged via the GitHub path")
        self.assertNotEqual(report.action, "Pruned", "must not execute git worktree remove on a diverged worktree")
        remove_calls = [c for c in mock_run_git.call_args_list if "remove" in c.args[1]]
        self.assertEqual(remove_calls, [], "git worktree remove must never be invoked for a SHA-mismatched worktree")

    def test_process_repository_prunes_on_execute_when_sha_matches(self):
        """Exact SHA match + --execute must actually invoke git worktree remove
        (happy-path counterpart to the mismatch-rejection test above)."""
        wt = pmw.WorktreeInfo(
            Path("/repo/.worktrees/merged-branch"),
            "cafebabe00000000000000000000000000000000",
            "merged-branch",
        )

        with patch("prune_merged_worktrees.get_worktrees", return_value=[wt]), \
             patch("prune_merged_worktrees.check_mid_operation", return_value=(False, "")), \
             patch("prune_merged_worktrees.check_clean", return_value=True), \
             patch("prune_merged_worktrees.get_origin_info", return_value=("git@github.com:es6kr/skills.git", "github", "es6kr/skills")), \
             patch("prune_merged_worktrees.get_default_upstream", return_value=None), \
             patch("prune_merged_worktrees.check_github_merged", return_value={
                 "number": 101,
                 "url": "https://github.com/es6kr/skills/pull/101",
                 "headRefOid": wt.head_sha,  # exact match
             }), \
             patch("prune_merged_worktrees.run_git") as mock_run_git:
            mock_run_git.side_effect = lambda repo_dir, args: (
                (0, "/repo", "") if args[:2] == ["rev-parse", "--show-toplevel"] else (0, "", "")
            )
            reports = pmw.process_repository(Path("/repo"), execute=True, delete_branch=False)

        self.assertEqual(len(reports), 1)
        report = reports[0]
        self.assertTrue(report.is_merged)
        self.assertEqual(report.action, "Pruned")
        remove_calls = [c for c in mock_run_git.call_args_list if "remove" in c.args[1]]
        self.assertEqual(len(remove_calls), 1, "git worktree remove must be invoked exactly once on a matched, execute=True worktree")


if __name__ == "__main__":
    unittest.main()
