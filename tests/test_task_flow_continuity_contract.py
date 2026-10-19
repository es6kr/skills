"""Static instruction conformance only; no agent behavior or live PM proof.

Each C1-C10 record pins a transition and its expected instruction obligations.
The source clauses are checked in their real owner files, not in a fake runtime.
Runnable with unittest or pytest; requires no third-party packages.
"""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/task_flow_continuity.json").read_text())

def normalized(text):
    return " ".join(text.split()).casefold()

class ContinuityContractTests(unittest.TestCase):
    def test_fixture_identity_and_limits(self):
        self.assertEqual([c["id"] for c in FIXTURE["cases"]], [f"C{i}" for i in range(1, 11)])
        self.assertEqual(FIXTURE["evidence_kind"], "instruction-conformance")
        self.assertIn("not agent behavioral", FIXTURE["limitation"])
        for case in FIXTURE["cases"]:
            for field in ("transition", "input", "expected", "required_clauses"):
                self.assertTrue(case[field], (case["id"], field))

    def test_report_projection_is_complete(self):
        source = normalized((ROOT / "skills/task-exec/verify.md").read_text())
        for field in FIXTURE["report_fields"]:
            with self.subTest(field=field):
                self.assertIn(normalized(field), source)
        self.assertIn("not a new shared runtime schema", source)

    def test_evidence_kinds_are_not_promoted(self):
        source = normalized((ROOT / "skills/task-exec/verify.md").read_text())
        self.assertIn("source/static/offline/live", source)
        self.assertIn("instruction conformance is not agent behavioral proof", source)

    def test_green_is_not_unconditional_tracker_done(self):
        source = normalized((ROOT / "skills/task-exec/delivery.md").read_text())
        self.assertNotIn("**backlog status update**: mark task as completed", source)
        self.assertIn("verified implementation, delivery, acceptance and canonical done are separate", source)
        self.assertIn("existing pm acceptance receipt", source)
        self.assertIn("missing acceptance remains pending", source)

    def test_feature_range_guard_survives(self):
        source = normalized((ROOT / "skills/task-exec/delivery.md").read_text())
        for clause in ("pinned base sha", "approved final commit count", "explicit allowed paths",
                       "require exit zero", "retain the json receipt", "clean state alone",
                       "separate native allow/block receipts", "immediately before publication",
                       "local completion alone never grants it"):
            with self.subTest(clause=clause):
                self.assertIn(clause, source)

    def test_changed_owner_links_resolve(self):
        for rel in ("task-flow/pipeline.md", "task-plan/review.md", "task-exec/gate.md",
                    "task-exec/verify.md", "task-exec/delivery.md"):
            path = ROOT / "skills" / rel
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text()):
                if not target.startswith(("http:", "https:", "#")):
                    self.assertTrue((path.parent / target.split("#")[0]).exists(), (rel, target))

def scenario_test(case):
    def test(self):
        for rel, clauses in case["required_clauses"].items():
            source = normalized((ROOT / rel).read_text())
            for clause in clauses:
                with self.subTest(scenario=case["id"], owner=rel, obligation=clause):
                    self.assertIn(normalized(clause), source, case["expected"])
    return test

for case in FIXTURE["cases"]:
    setattr(ContinuityContractTests, "test_" + case["id"], scenario_test(case))

if __name__ == "__main__":
    unittest.main()
