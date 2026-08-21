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

from skills.consolidate.scripts.verify_consolidate import ConsolidateValidator


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
        self.assertTrue(any("missing superpowers" in err for err in validator.errors))

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
