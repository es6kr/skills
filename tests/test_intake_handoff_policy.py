"""Source-contract regressions; do not claim live agent enforcement."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class IntakeHandoffPolicy(unittest.TestCase):
    def test_review_preserves_approval_and_conditional_ask(self):
        text = (ROOT / "skills/task-plan/review.md").read_text()
        for rule in ("No recommendation means no needless Intake ask",
                     "native ask BEFORE creation", "never duplicate it",
                     "Reuse explicit authorization for the exact action",
                     "retain original local files", "Do not fabricate missing artifacts"):
            with self.subTest(rule=rule):
                self.assertIn(rule, text)

    def test_draft_does_not_treat_read_only_as_comment_permission(self):
        text = (ROOT / "skills/fix-plan/draft.md").read_text()
        self.assertNotIn("NOT posting reference comments", text)
        self.assertNotIn("containing the CollabMD viewer link, local artifact path", text)
        for rule in ("read-only planning does not authorize comments",
                     "report linkage pending without blocking plan delivery",
                     "verified accessible CollabMD content",
                     "never fabricate documents or recovery",
                     "Mandatory PR/completed audit remains a surfaced need",
                     "../task-plan/review.md#plan-delivery-and-optional-intake"):
            with self.subTest(rule=rule):
                self.assertIn(rule, text)

if __name__ == "__main__":
    unittest.main()
