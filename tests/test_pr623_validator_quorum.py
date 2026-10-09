"""PR623: independent review quorum never substitutes for source coverage."""
import copy
import json
import re
import shlex
import subprocess
import textwrap
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skills.consolidate.scripts import verify_consolidate as mod


class QuorumTests(unittest.TestCase):
    def setUp(self):
        self.inline = [
            {"id": 101, "pull_request_review_id": 11, "user": {"login": "Copilot"},
             "path": "a.py", "line": 1, "body": "Retry can loop forever."},
            {"id": 102, "pull_request_review_id": 12, "user": {"login": "coderabbitai[bot]"},
             "path": "b.py", "line": 2, "body": "Missing input validation."},
        ]
        self.reviews = [
            {"id": 11, "state": "COMMENTED", "submitted_at": "2026-10-01T00:00:00Z",
             "commit_id": "abc1234", "user": {"login": "Copilot"}, "body": "Reviewed changes: retry loop."},
            {"id": 12, "state": "CHANGES_REQUESTED", "submitted_at": "2026-10-01T00:01:00Z",
             "commit_id": "abc1234", "user": {"login": "coderabbitai[bot]"}, "body": "Actionable comments posted: 1"},
        ]
        self.summary = {"id": 20, "created_at": "2026-10-01T00:02:00Z", "body": """## AI Review Summary — [receiving-code-review](https://x/receiving-code-review)
<!-- consolidate:verified -->
Copilot — 1 inline comments; CodeRabbit — 1 inline comments
| # | Source / Classification | Location | Finding | Status |
|---|---|---|---|---|
| 1 | [Copilot](https://github.com/o/r/pull/623#discussion_r101) | `a.py:1` | retry loop | Pending |
| 2 | [CodeRabbit](https://github.com/o/r/pull/623#discussion_r102) | `b.py:2` | validation | Pending |
"""}

    def validate(self):
        validator = mod.ConsolidateValidator(623, "o/r")
        with patch.object(mod, "run_gh_api", side_effect=[self.inline, [self.summary], self.reviews]), patch.object(mod, "git_sha_exists", return_value=True):
            result = validator.validate()
        return result, validator.errors

    def test_different_review_commits_do_not_form_quorum(self):
        self.reviews[1]["commit_id"] = "def5678"
        self.assertFalse(self.validate()[0])

    def test_completed_independent_sources_allow_summary_only(self):
        ok, errors = self.validate()
        self.assertTrue(ok, errors)

    def test_same_engine_variants_do_not_make_quorum(self):
        self.reviews[0]["user"]["login"] = "coderabbit-cli[bot]"
        ok, errors = self.validate()
        self.assertFalse(ok)
        self.assertTrue(any("quorum" in e.lower() or "Missing Internal" in e for e in errors), errors)

    def test_nonreviews_never_make_quorum(self):
        for body, state in [("", "COMMENTED"), ("Review skipped: draft", "COMMENTED"),
                            ("Review encountered an error", "COMMENTED"),
                            ("![green badge](https://x/badge)", "COMMENTED"),
                            ("## Walkthrough\nChanges overview", "COMMENTED"),
                            ("Reviewed changes", "PENDING"), ("Reviewed changes", "DISMISSED")]:
            with self.subTest(body=body, state=state):
                self.reviews[1]["body"] = body
                self.reviews[1]["state"] = state
                self.assertFalse(self.validate()[0])

    def test_review_after_summary_does_not_supply_causality(self):
        self.reviews[1]["submitted_at"] = "2026-10-01T00:03:00Z"
        self.assertFalse(self.validate()[0])

    def test_padded_rows_cannot_replace_missing_source_id(self):
        self.summary["body"] = self.summary["body"].replace("discussion_r102", "discussion_r999")
        self.assertFalse(self.validate()[0])

    def test_id_in_prose_or_finding_cell_is_not_source_coverage(self):
        self.summary["body"] = self.summary["body"].replace(
            "[CodeRabbit](https://github.com/o/r/pull/623#discussion_r102)", "CodeRabbit")
        self.summary["body"] += "\nhttps://github.com/o/r/pull/623#discussion_r102\n"
        self.summary["body"] = self.summary["body"].replace("| validation |", "| https://github.com/o/r/pull/623#discussion_r102 |")
        self.assertFalse(self.validate()[0])

    def test_wrong_engine_cannot_claim_source_id(self):
        self.summary["body"] = self.summary["body"].replace("[CodeRabbit]", "[Copilot]")
        self.assertFalse(self.validate()[0])

    def test_wrong_pr_link_cannot_claim_source_id(self):
        self.summary["body"] = self.summary["body"].replace("pull/623#discussion_r102", "pull/624#discussion_r102")
        self.assertFalse(self.validate()[0])

    def test_location_source_link_with_engine_attribution_is_covered(self):
        self.summary["body"] = self.summary["body"].replace(
            "[CodeRabbit](https://github.com/o/r/pull/623#discussion_r102)", "CodeRabbit").replace(
            "`b.py:2`", "[b.py:2](https://github.com/o/r/pull/623#discussion_r102)")
        ok, errors = self.validate()
        self.assertTrue(ok, errors)

    def test_local_only_rows_are_allowed(self):
        self.summary["body"] += "| 3 | Local reviewer | `c.py:3` | local finding | Deferred (issue #8) |\n"
        self.assertTrue(self.validate()[0])

    def test_historical_idless_finding_requires_source_and_exact_location(self):
        del self.inline[1]["id"]
        self.summary["body"] = self.summary["body"].replace("`b.py:2`", "`b.py:22`")
        self.assertFalse(self.validate()[0])

    def test_summary_only_preserves_other_validation_gates(self):
        original = self.summary["body"]
        for mutation, expected in [
            (original.replace("Copilot — 1 inline", "Copilot — 2 inline"), "Reviewer Matrix mismatch"),
            (original.replace("| 2 | [CodeRabbit]", "| not-a-finding | [CodeRabbit]"), "row count mismatch"),
            (original + "\nUse gh pr merge 623\n", "raw 'gh pr merge'"),
        ]:
            with self.subTest(expected=expected):
                self.summary["body"] = mutation
                ok, errors = self.validate()
                self.assertFalse(ok)
                self.assertTrue(any(expected in e for e in errors), errors)

    def test_cited_sha_is_still_checked_on_summary_only(self):
        self.summary["body"] += "\nFixed in commit deadbee\n"
        validator = mod.ConsolidateValidator(623, "o/r")
        with patch.object(mod, "run_gh_api", side_effect=[self.inline, [self.summary], self.reviews]), patch.object(mod, "git_sha_exists", return_value=False):
            self.assertFalse(validator.validate())
        self.assertTrue(any("non-existent commit SHA" in e for e in validator.errors))

    def test_unlinked_noise_body_does_not_supply_substantive_review(self):
        self.reviews[1]["body"] = "Dispatch started."
        self.inline[1]["pull_request_review_id"] = 999
        self.assertFalse(self.validate()[0])

    def test_latest_summary_is_validated_not_oldest(self):
        old = copy.deepcopy(self.summary)
        old["created_at"] = "2026-10-01T00:01:30Z"
        self.summary["body"] = self.summary["body"].replace("| Pending |", "| Verified |")
        validator = mod.ConsolidateValidator(623, "o/r")
        with patch.object(mod, "run_gh_api", side_effect=[self.inline, [self.summary, old], self.reviews]):
            self.assertFalse(validator.validate())
        self.assertTrue(any("outside the post.md" in e for e in validator.errors))

    def test_status_gate_still_runs_on_summary_only(self):
        self.summary["body"] = self.summary["body"].replace("| Pending |", "| Verified |")
        ok, errors = self.validate()
        self.assertFalse(ok)
        self.assertTrue(any("outside the post.md" in e for e in errors), errors)


class ApiAndMergeTests(unittest.TestCase):
    def test_api_paginates_and_flattens_without_unsupported_repo_flag(self):
        pages = [[{"id": 1}], [{"id": 2}]]
        with patch.object(mod.subprocess, "run", return_value=Mock(stdout=json.dumps(pages))) as run:
            result = mod.run_gh_api("repos/o/r/pulls/623/comments", "o/r")
        self.assertEqual(result, [{"id": 1}, {"id": 2}])
        command = run.call_args.args[0]
        self.assertIn("--paginate", command)
        self.assertIn("--slurp", command)
        self.assertNotIn("-R", command)
        self.assertIn("repos/o/r/pulls/623/comments", command)

    def test_documented_lookup_executes_and_selects_latest_across_pages_and_media(self):
        text = (Path(__file__).resolve().parents[1] / "skills/github-flow/merge.md").read_text()
        blocks = re.findall(r"```bash\n(.*?)```", text, re.S)
        block = textwrap.dedent(next(b for b in blocks if "latest_summary()" in b))
        block = block.replace("{owner}/{repo}", "o/r").replace("<PR_NUMBER>", "623")
        title = "## AI Review Summary — [receiving-code-review](https://x/receiving-code-review)"
        old = {"id": 1, "created_at": "2026-10-01T00:00:00Z", "body": title}
        recent = {"id": 2, "created_at": "2026-10-01T00:01:00Z", "body": title}
        formal = {"id": 3, "submitted_at": "2026-10-01T00:02:00Z", "body": title}
        prelude = "gh() { case \"$2\" in */issues/*) printf '%s' " + shlex.quote(json.dumps([[recent], [old]])) + ";; */pulls/*) printf '%s' " + shlex.quote(json.dumps([[formal]])) + ";; *) return 99;; esac; }\n"
        result = subprocess.run(["bash", "-c", prelude + block], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["id"], 3)
        self.assertEqual(json.loads(result.stdout)["medium"], "review")

    def test_merge_instructions_do_not_select_oldest_summary(self):
        text = (Path(__file__).resolve().parents[1] / "skills/github-flow/merge.md").read_text()
        self.assertNotIn('[.[] | select(.body | startswith("## AI Review Summary")) | .body][0]', text)
        self.assertIn("sort_by(.created_at // .submitted_at)", text)
        self.assertIn("--paginate --slurp", text)


if __name__ == "__main__":
    unittest.main()
