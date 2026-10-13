"""Unit tests for verify_consolidate.py mechanical validation script."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skills.consolidate.scripts.verify_consolidate import (
    INTERNAL_SLUG,
    SUMMARY_SLUG,
    ConsolidateValidator,
    is_internal_review,
    titled_as,
    titled_as_internal_by_engine,
)


class TestVerifyConsolidate(unittest.TestCase):
    def setUp(self):
        self.sample_inline_comments = [
            {"user": {"login": "Copilot"}, "path": "file1.py", "line": 10, "body": "Copilot comment 1"},
            {"user": {"login": "Copilot"}, "path": "file2.py", "line": 20, "body": "Copilot comment 2"},
            {"user": {"login": "coderabbitai[bot]"}, "path": "file3.py", "line": 30, "body": "CodeRabbit comment 1"},
        ]

        self.sample_valid_issue_comments = [
            {
                "created_at": "2026-08-21T00:00:00Z",
                "body": """## Internal Code Review — [requesting-code-review](https://skills.sh/obra/superpowers/requesting-code-review)
<!-- consolidate:verified -->

### Findings
#### 1. `file4.py:40` — Internal finding 1
Detail 1
"""
            },
            {
                "created_at": "2026-08-21T00:01:00Z",
                "body": """## AI Review Summary — [receiving-code-review](https://skills.sh/obra/superpowers/receiving-code-review)
<!-- consolidate:verified -->

### Reviewer Matrix
| Reviewer | Type | Status | Findings |
|---|---|---|---|
| **GitHub Copilot** | External AI | Completed | 2 inline comments |
| **CodeRabbit** | External AI | Completed | 1 inline comment |
| **superpowers code-reviewer** | Internal | Completed | 1 finding |

### Consolidated Findings
| # | Source | File | Scope | Type | Status | Details |
|---|---|---|---|---|---|---|
| 1 | copilot | `file1.py:10` | In diff | Type | Pending | detail 1 |
| 2 | copilot | `file2.py:20` | In diff | Type | Pending | detail 2 |
| 3 | coderabbit | `file3.py:30` | In diff | Type | Pending | detail 3 |
| 4 | superpowers | `file4.py:40` | In diff | Type | Pending | internal 1 |

### Merge Recommendation
Recommend merge via `/github-flow merge 123`.
"""
            }
        ]

    @patch("skills.consolidate.scripts.verify_consolidate.run_gh_api")
    @patch("skills.consolidate.scripts.verify_consolidate.git_sha_exists", return_value=True)
    def test_validator_passes_on_valid_data(self, mock_sha, mock_api):
        mock_api.side_effect = [self.sample_inline_comments, self.sample_valid_issue_comments]
        validator = ConsolidateValidator(pr_num=123, repo="es6kr/skills")
        self.assertTrue(validator.validate())
        self.assertEqual(len(validator.errors), 0)

    @patch("skills.consolidate.scripts.verify_consolidate.run_gh_api")
    def test_validator_fails_on_missing_superpowers_in_table(self, mock_api):
        internal_review = self.sample_valid_issue_comments[0]
        # Summary missing superpowers row (only 3 rows instead of 4)
        summary = {
            "created_at": "2026-08-21T00:01:00Z",
            "body": """## AI Review Summary — [receiving-code-review](https://skills.sh/obra/superpowers/receiving-code-review)
<!-- consolidate:verified -->

### Reviewer Matrix
| Reviewer | Type | Status | Findings |
|---|---|---|---|
| **GitHub Copilot** | External AI | Completed | 2 inline comments |
| **CodeRabbit** | External AI | Completed | 1 inline comment |
| **superpowers code-reviewer** | Internal | Completed | 1 finding |

### Consolidated Findings
| # | Source | File | Scope | Type | Status | Details |
|---|---|---|---|---|---|---|
| 1 | copilot | `file1.py:10` | In diff | Type | Pending | detail 1 |
| 2 | copilot | `file2.py:20` | In diff | Type | Pending | detail 2 |
| 3 | coderabbit | `file3.py:30` | In diff | Type | Pending | detail 3 |
"""
        }
        mock_api.side_effect = [self.sample_inline_comments, [internal_review, summary]]
        validator = ConsolidateValidator(pr_num=123, repo="es6kr/skills")
        self.assertFalse(validator.validate())
        self.assertTrue(any("row count mismatch" in err for err in validator.errors))
        self.assertTrue(any("missing Internal Code Review findings" in err for err in validator.errors))

    @patch("skills.consolidate.scripts.verify_consolidate.run_gh_api")
    def test_validator_fails_on_out_of_order_comments(self, mock_api):
        # Swap created_at so Summary appears before Internal Review
        out_of_order_comments = [
            dict(self.sample_valid_issue_comments[0], created_at="2026-08-21T00:05:00Z"),
            dict(self.sample_valid_issue_comments[1], created_at="2026-08-21T00:00:00Z"),
        ]
        mock_api.side_effect = [self.sample_inline_comments, out_of_order_comments]
        validator = ConsolidateValidator(pr_num=123, repo="es6kr/skills")
        self.assertFalse(validator.validate())
        self.assertTrue(any("Chronological order error" in err for err in validator.errors))


if __name__ == "__main__":
    unittest.main()


class TestTitleLineArtifactDetection(unittest.TestCase):
    """Artifact identity comes from the title line, not from a substring anywhere
    in the body.

    Regression for the es6kr/claude-plugins PR #38 miss: a single fabricated
    Summary that merely named both protocols in a bullet satisfied the old
    whole-body substring filters for BOTH artifacts, so `internal_reviews[-1]`
    and `summaries[-1]` resolved to the same comment, the chronological check
    compared a timestamp with itself, and "Missing Internal Code Review comment"
    stayed silent on a PR that had no Internal Review at all.
    """

    INTERNAL = ("## Internal Code Review — [requesting-code-review]"
                "(https://skills.sh/obra/superpowers/requesting-code-review)\n"
                "<!-- consolidate:verified -->\nfindings\n")
    SUMMARY = ("## AI Review Summary — [receiving-code-review]"
               "(https://skills.sh/obra/superpowers/receiving-code-review)\n"
               "<!-- consolidate:verified -->\ntable\n")

    def test_proper_titles_classify_to_exactly_one_artifact(self):
        self.assertTrue(titled_as(self.INTERNAL, INTERNAL_SLUG))
        self.assertFalse(titled_as(self.INTERNAL, SUMMARY_SLUG))
        self.assertTrue(titled_as(self.SUMMARY, SUMMARY_SLUG))
        self.assertFalse(titled_as(self.SUMMARY, INTERNAL_SLUG))

    def test_caller_custom_review_title_still_recognised(self):
        """post.md permits a caller-supplied title; the link is what identifies it."""
        body = ("## Code Review — [requesting-code-review]"
                "(https://skills.sh/obra/superpowers/requesting-code-review)\nfindings\n")
        self.assertTrue(titled_as(body, INTERNAL_SLUG))

    def test_prose_mention_of_both_slugs_is_neither_artifact(self):
        """The PR #38 body verbatim in shape: a heading with no link, and both
        protocol names mentioned on a later line."""
        body = ("# AI Review Summary — PR #38 (Integration: `develop -> main`)\n\n"
                "- **Review Protocols**: `requesting-code-review` & `receiving-code-review`\n")
        self.assertFalse(titled_as(body, INTERNAL_SLUG))
        self.assertFalse(titled_as(body, SUMMARY_SLUG))

    def test_summary_discussing_the_pairing_stays_a_summary(self):
        """A Summary is allowed to explain the requesting/receiving pairing in its
        body without being misread as the Internal Review — the case that made the
        old filter actively hostile to an honest write-up."""
        body = self.SUMMARY + "\nThe requesting-code-review skill was never invoked.\n"
        self.assertTrue(titled_as(body, SUMMARY_SLUG))
        self.assertFalse(titled_as(body, INTERNAL_SLUG))

    def test_heading_without_link_is_not_an_artifact(self):
        self.assertFalse(titled_as("## Internal Code Review\nfindings\n", INTERNAL_SLUG))

    # --- engine-named Code Review (internal.md's suffix-drop shape) --------------
    # internal.md FORBIDS the requesting-code-review link when the body carries
    # bot-layer content, so requiring that link unconditionally made the skill and
    # this verifier unsatisfiable at the same time. The replacement is a conjunction,
    # not a looser single check: marker AND engine-named heading AND no "Summary".

    ENGINE_NAMED = ("## Code Review (CodeRabbit CLI local)\n"
                    "<!-- consolidate:verified -->\nfindings\n")

    def test_engine_named_review_is_recognised_without_the_framework_link(self):
        self.assertFalse(titled_as(self.ENGINE_NAMED, INTERNAL_SLUG))
        self.assertTrue(titled_as_internal_by_engine(self.ENGINE_NAMED))
        self.assertTrue(is_internal_review(self.ENGINE_NAMED))

    def test_engine_named_review_without_the_marker_is_rejected(self):
        """The marker is one of the conjunction's terms, not decoration."""
        body = "## Code Review (CodeRabbit CLI local)\nfindings\n"
        self.assertFalse(titled_as_internal_by_engine(body))
        self.assertFalse(is_internal_review(body))

    def test_code_review_heading_naming_no_engine_is_rejected(self):
        """A bare 'Code Review' heading must not register just by carrying the marker."""
        body = "## Code Review\n<!-- consolidate:verified -->\nfindings\n"
        self.assertFalse(titled_as_internal_by_engine(body))
        self.assertFalse(is_internal_review(body))

    def test_engine_named_heading_claiming_summary_is_rejected(self):
        """post.md reserves the word Summary for the Step 7 artifact."""
        body = ("## Code Review Summary (CodeRabbit CLI local)\n"
                "<!-- consolidate:verified -->\nfindings\n")
        self.assertFalse(titled_as_internal_by_engine(body))
        self.assertFalse(is_internal_review(body))

    def test_the_summary_artifact_is_not_mistaken_for_an_engine_named_review(self):
        """The Summary carries the marker too — only the heading separates them."""
        self.assertFalse(titled_as_internal_by_engine(self.SUMMARY))
        self.assertFalse(is_internal_review(self.SUMMARY))

    def test_framework_linked_review_still_passes_through_is_internal_review(self):
        self.assertTrue(is_internal_review(self.INTERNAL))

    def test_missing_internal_review_is_reported_with_a_near_miss_hint(self):
        issue_comments = [
            {"id": 1, "created_at": "2026-08-29T00:00:00Z", "body": "## Internal Code Review\nno link\n"},
            {"id": 2, "created_at": "2026-08-29T01:00:00Z", "body": self.SUMMARY},
        ]
        v = ConsolidateValidator(pr_num=1, repo="o/r")
        with patch("skills.consolidate.scripts.verify_consolidate.run_gh_api") as gh:
            gh.side_effect = [[], issue_comments]
            v.validate()
        joined = " ".join(v.errors)
        self.assertIn("Missing Internal Code Review comment", joined)
        self.assertIn("comment 1", joined)

    def test_one_comment_titled_as_both_is_rejected(self):
        both = ("## Review — [requesting-code-review](https://x/requesting-code-review) "
                "and [receiving-code-review](https://x/receiving-code-review)\nbody\n")
        v = ConsolidateValidator(pr_num=1, repo="o/r")
        with patch("skills.consolidate.scripts.verify_consolidate.run_gh_api") as gh:
            gh.side_effect = [[], [{"id": 9, "created_at": "2026-08-29T00:00:00Z", "body": both}]]
            v.validate()
        self.assertIn("titled as BOTH", " ".join(v.errors))


class TestFindingSourceCoverage(unittest.TestCase):
    """Every source that actually produced findings must be countable.

    Three sources were invisible to the validator and each one silently forced
    the expected-row arithmetic below the real finding count, so an honest
    Summary listing all of them failed the gate:

    1. An Internal Code Review posted as a *review* (internal.md routes it there
       whenever line-specific Critical/Important findings exist, because only the
       reviews API carries inline annotations) was searched for in issue comments
       only.
    2. A bot's *suppressed* findings live in the review body, not in
       `pulls/<N>/comments`, so they were never counted.
    3. A human reviewer's own review body was not counted at all.
    """

    INTERNAL_AS_REVIEW = {
        "user": {"login": "DrumRobot"},
        "submitted_at": "2026-09-12T00:00:00Z",
        "body": """## Internal Code Review — [requesting-code-review](https://skills.sh/obra/superpowers/requesting-code-review)
<!-- consolidate:verified -->

#### IR-1 · Potential | Critical — first internal finding
detail
#### IR-2 · Potential | Important — second internal finding
detail
""",
    }

    COPILOT_REVIEW_WITH_SUPPRESSED = {
        "user": {"login": "copilot-pull-request-reviewer[bot]"},
        "submitted_at": "2026-09-12T00:00:10Z",
        "body": """### Changes recommended

<details>
<summary>Review details</summary>

### Suppressed comments (3)

**scripts/a.py:10**
* suppressed finding one
**scripts/b.py:20**
* suppressed finding two
**scripts/c.py:30**
* suppressed finding three
</details>
""",
    }

    HUMAN_REVIEW = {
        "user": {"login": "daegunjhy"},
        "submitted_at": "2026-09-12T00:00:20Z",
        "body": "This looks wrong to me — the retry loop can spin forever.",
    }

    SUMMARY = {
        "created_at": "2026-09-12T00:01:00Z",
        "body": """## AI Review Summary — [receiving-code-review](https://skills.sh/obra/superpowers/receiving-code-review)
<!-- consolidate:verified -->

> Reviewer matrix: copilot — 1 inline comments (+3 suppressed) · daegunjhy — 1 review · superpowers — 2 findings

### Consolidated Findings
| # | Source | Type | Location | Finding | Status |
|---|---|---|---|---|---|
| 1 | copilot | Potential | `file1.py:10` | inline one | 🔴 Pending |
| 2 | copilot | Potential | `scripts/a.py:10` | suppressed one | 🔴 Pending |
| 3 | copilot | Potential | `scripts/b.py:20` | suppressed two | 🔴 Pending |
| 4 | copilot | Potential | `scripts/c.py:30` | suppressed three | 🔴 Pending |
| 5 | @daegunjhy | Potential | `file9.py:90` | human review point | 🔴 Pending |
| 6 | superpowers | Potential | `x.py:1` | internal one | 🔴 Pending |
| 7 | superpowers | Potential | `y.py:2` | internal two | 🔴 Pending |

### Merge Recommendation
Hold — address the Pending findings first. Merge via `/github-flow merge 123`.
""",
    }

    ONE_INLINE = [
        {"user": {"login": "Copilot"}, "path": "file1.py", "line": 10, "body": "inline one"},
    ]

    @patch("skills.consolidate.scripts.verify_consolidate.run_gh_api")
    @patch("skills.consolidate.scripts.verify_consolidate.git_sha_exists", return_value=True)
    def test_internal_review_posted_as_review_is_found(self, mock_sha, mock_api):
        """internal.md routes the Internal Review to the reviews API when inline
        targets exist. Searching issue comments only reports it as missing."""
        mock_api.side_effect = [
            self.ONE_INLINE,
            [self.SUMMARY],
            [self.INTERNAL_AS_REVIEW, self.COPILOT_REVIEW_WITH_SUPPRESSED, self.HUMAN_REVIEW],
        ]
        validator = ConsolidateValidator(pr_num=123, repo="es6kr/skills")
        validator.validate()
        self.assertFalse(
            any("Missing Internal Code Review" in e for e in validator.errors),
            f"Internal Review posted as a review should be found. errors={validator.errors}",
        )

    @patch("skills.consolidate.scripts.verify_consolidate.run_gh_api")
    @patch("skills.consolidate.scripts.verify_consolidate.git_sha_exists", return_value=True)
    def test_suppressed_and_human_and_internal_all_counted(self, mock_sha, mock_api):
        """1 inline + 3 suppressed + 1 human review + 2 internal = 7 rows."""
        mock_api.side_effect = [
            self.ONE_INLINE,
            [self.SUMMARY],
            [self.INTERNAL_AS_REVIEW, self.COPILOT_REVIEW_WITH_SUPPRESSED, self.HUMAN_REVIEW],
        ]
        validator = ConsolidateValidator(pr_num=123, repo="es6kr/skills")
        ok = validator.validate()
        self.assertTrue(
            ok and not validator.errors,
            f"7 real findings must reconcile with 7 table rows. errors={validator.errors}",
        )

    @patch("skills.consolidate.scripts.verify_consolidate.run_gh_api")
    @patch("skills.consolidate.scripts.verify_consolidate.git_sha_exists", return_value=True)
    def test_internal_findings_counted_regardless_of_header_style(self, mock_sha, mock_api):
        """`#### IR-1 ·` is as valid a finding header as `#### 1.`."""
        mock_api.side_effect = [
            self.ONE_INLINE,
            [self.SUMMARY],
            [self.INTERNAL_AS_REVIEW, self.COPILOT_REVIEW_WITH_SUPPRESSED, self.HUMAN_REVIEW],
        ]
        validator = ConsolidateValidator(pr_num=123, repo="es6kr/skills")
        ok = validator.validate()
        self.assertTrue(
            ok and not validator.errors,
            f"IR-style headers must count as internal findings. errors={validator.errors}",
        )


class TestInlineAccountingEdgeCases(unittest.TestCase):
    """Two defects found by running the validator against a real consolidated PR."""

    @patch("skills.consolidate.scripts.verify_consolidate.run_gh_api")
    @patch("skills.consolidate.scripts.verify_consolidate.git_sha_exists", return_value=True)
    def test_internal_reviews_own_inline_comment_is_not_double_counted(self, mock_sha, mock_api):
        """When the Internal Review is posted as a review, its inline annotations
        land in pulls/<N>/comments too. They are the same findings already counted
        as internal findings, so counting them again inflates the expected total
        and demands a row that must not exist."""
        internal = {
            "id": 999,
            "user": {"login": "DrumRobot"},
            "submitted_at": "2026-09-12T00:00:00Z",
            "body": """## Internal Code Review — [requesting-code-review](https://skills.sh/obra/superpowers/requesting-code-review)
<!-- consolidate:verified -->

#### IR-1 · the one internal finding
detail
""",
        }
        summary = {
            "created_at": "2026-09-12T00:01:00Z",
            "body": """## AI Review Summary — [receiving-code-review](https://skills.sh/obra/superpowers/receiving-code-review)
<!-- consolidate:verified -->

> Reviewer matrix: copilot — 1 inline comments

### Consolidated Findings
| # | Source | Location | Finding | Status |
|---|---|---|---|---|
| 1 | copilot | `a.py:1` | external one | 🔴 Pending |
| 2 | superpowers | `b.py:2` | internal one | 🔴 Pending |

### Merge Recommendation
Hold. Merge via `/github-flow merge 123`.
""",
        }
        inline = [
            {"user": {"login": "Copilot"}, "path": "a.py", "line": 1, "body": "external one"},
            # the Internal Review's OWN inline annotation
            {"user": {"login": "DrumRobot"}, "path": "b.py", "line": 2,
             "body": "internal one", "pull_request_review_id": 999},
        ]
        mock_api.side_effect = [inline, [summary], [internal]]
        validator = ConsolidateValidator(pr_num=123, repo="es6kr/skills")
        ok = validator.validate()
        self.assertTrue(ok and not validator.errors, f"errors={validator.errors}")

    @patch("skills.consolidate.scripts.verify_consolidate.run_gh_api")
    @patch("skills.consolidate.scripts.verify_consolidate.git_sha_exists", return_value=True)
    def test_escaped_pipe_inside_cell_does_not_shift_status_column(self, mock_sha, mock_api):
        """A finding that quotes a regex needs `\\|` inside a cell. Splitting on
        every pipe shifts every later column, so the Status check reads a regex
        fragment and reports an off-contract value on a correct table."""
        internal = {
            "created_at": "2026-09-12T00:00:00Z",
            "body": """## Internal Code Review — [requesting-code-review](https://skills.sh/obra/superpowers/requesting-code-review)
<!-- consolidate:verified -->

#### 1. the one internal finding
detail
""",
        }
        summary = {
            "created_at": "2026-09-12T00:01:00Z",
            "body": r"""## AI Review Summary — [receiving-code-review](https://skills.sh/obra/superpowers/receiving-code-review)
<!-- consolidate:verified -->

> Reviewer matrix: copilot — 1 inline comments

### Consolidated Findings
| # | Source | Location | Finding | Status |
|---|---|---|---|---|
| 1 | copilot | `a.py:1` | regex `(?:x\|PAT)\s{0,2}(?:\btoken\b\|tok)` is too narrow | 🔴 Pending |
| 2 | superpowers | `b.py:2` | internal one | 🔴 Pending |

### Merge Recommendation
Hold. Merge via `/github-flow merge 123`.
""",
        }
        inline = [{"user": {"login": "Copilot"}, "path": "a.py", "line": 1, "body": "x"}]
        mock_api.side_effect = [inline, [internal, summary], []]
        validator = ConsolidateValidator(pr_num=123, repo="es6kr/skills")
        validator.validate()
        self.assertFalse(
            any("outside the post.md contract" in e for e in validator.errors),
            f"escaped pipe must not shift the Status column. errors={validator.errors}",
        )

    @patch("skills.consolidate.scripts.verify_consolidate.git_sha_exists", return_value=True)
    @patch("skills.consolidate.scripts.verify_consolidate.run_gh_api")
    def test_validator_supports_three_line_source_classification_column(self, mock_api, mock_sha):
        internal = {
            "created_at": "2026-10-05T00:00:00Z",
            "body": """## Internal Code Review — [requesting-code-review](https://skills.sh/obra/superpowers/requesting-code-review)
<!-- consolidate:verified -->

### Findings
#### 1. `b.py:2` — internal finding
detail
""",
        }
        summary = {
            "created_at": "2026-10-05T00:01:00Z",
            "body": """## AI Review Summary — [receiving-code-review](https://skills.sh/obra/superpowers/receiving-code-review)
<!-- consolidate:verified -->

> Reviewer matrix: copilot — 1 inline comments

### Consolidated Findings
| # | Source / Classification | Location | Finding | Status |
|---|---|---|---|---|
| 1 | copilot<br>⚠️ Potential issue<br>🟠 Important | `a.py:1` | finding 1 | 🔴 Pending |
| 2 | superpowers<br>🛠️ Refactor<br>🟡 Minor | `b.py:2` | internal finding | 🟢 Fixed (commit abc1234) |

### Merge Recommendation
Hold. Merge via `/github-flow merge 123`.
""",
        }
        inline = [{"user": {"login": "Copilot"}, "path": "a.py", "line": 1, "body": "finding 1"}]
        mock_api.side_effect = [inline, [internal, summary], []]
        validator = ConsolidateValidator(pr_num=123, repo="es6kr/skills")
        self.assertTrue(validator.validate(), f"Validation failed with errors: {validator.errors}")
        self.assertEqual(len(validator.errors), 0)

    @patch("skills.consolidate.scripts.verify_consolidate.git_sha_exists", return_value=True)
    @patch("skills.consolidate.scripts.verify_consolidate.run_gh_api")
    def test_validator_fails_when_graph_review_causality_is_broken(self, mock_api, mock_sha):
        summary = {
            "id": 999,
            "created_at": "2026-10-05T00:01:00Z",
            "body": """## AI Review Summary — [receiving-code-review](https://skills.sh/obra/superpowers/receiving-code-review)
<!-- consolidate:verified -->

> Reviewer matrix: copilot — 1 inline comments

### Consolidated Findings
| # | Source / Classification | Location | Finding | Status |
|---|---|---|---|---|
| 1 | copilot<br>⚠️ Potential issue<br>🟠 Important | `a.py:1` | finding 1 | 🔴 Pending |

### Merge Recommendation
Hold. Merge via `/github-flow merge 123`.
""",
        }
        inline = [{"id": 1, "user": {"login": "Copilot"}, "path": "a.py", "line": 1, "body": "finding 1"}]
        # Only summary exists, no internal review
        mock_api.side_effect = [inline, [summary], []]
        validator = ConsolidateValidator(pr_num=123, repo="es6kr/skills")
        self.assertFalse(validator.validate())
        self.assertTrue(
            any("causal" in e.lower() or "disconnected" in e.lower() for e in validator.errors),
            f"Expected graph causal error in validator.errors, got: {validator.errors}",
        )

