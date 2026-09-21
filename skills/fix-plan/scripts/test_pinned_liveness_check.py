#!/usr/bin/env python3
"""Unit tests for pinned_liveness_check.py."""

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

import importlib.util
spec = importlib.util.spec_from_file_location("pinned_liveness_check", str(SCRIPT_DIR / "pinned_liveness_check.py"))
plc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plc)


RESOLVED_TRACKER = """# Fix Plan

> 📌 Pinned
> - **Mission A**: does X and Y <!-- pinned-backing: todo:"item one", deep:"item two" -->

## TODO

- [x] item one done

## Deep Tasks

- [BLOCKED:P1:selfable] unrelated other task

## Completed

- 2026-09-21 -- item two done (moved from Deep Tasks)
"""

OPEN_TRACKER = """# Fix Plan

> 📌 Pinned
> - **Mission A**: not done yet <!-- pinned-backing: todo:"item one", deep:"item two" -->

## TODO

- [ ] item one still open

## Deep Tasks

- [BLOCKED:P1:selfable] item two still open
"""

UNKNOWN_CITATION_TRACKER = """# Fix Plan

> 📌 Pinned
> - **Mission A**: mystery <!-- pinned-backing: todo:"item that does not exist" -->

## TODO

- [ ] unrelated item
"""

UNMONITORED_TRACKER = """# Fix Plan

> 📌 Pinned
> - **Mission A**: no marker here at all

## TODO

- [ ] unrelated item
"""

DEEP_TASKS_FALLBACK_TRACKER = """# Fix Plan

> 📌 Pinned
> - **Mission A**: done <!-- pinned-backing: todo:"item one" -->

## TODO

- [x] item one done

## Deep Tasks

- [PROMOTED] **Already promoted, skip me**
- [BLOCKED:P2:selfable] **Lower priority candidate**
- [BLOCKED:P0:external] **Highest priority candidate**
"""


def write_tracker(content):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name


class TestSplitSections(unittest.TestCase):
    def test_pinned_block_captured_before_first_heading(self):
        sections = plc.split_sections(RESOLVED_TRACKER)
        pinned = sections[plc.PINNED_KEY]
        self.assertTrue(any("Mission A" in line for line in pinned))
        self.assertNotIn("## TODO", "\n".join(pinned))

    def test_sections_split_by_heading(self):
        sections = plc.split_sections(RESOLVED_TRACKER)
        self.assertIn("TODO", sections)
        self.assertIn("Deep Tasks", sections)
        self.assertIn("Completed", sections)
        self.assertTrue(any("item one done" in l for l in sections["TODO"]))


class TestExtractMissions(unittest.TestCase):
    def test_marker_parsed_into_citations(self):
        sections = plc.split_sections(RESOLVED_TRACKER)
        missions = plc.extract_missions(sections[plc.PINNED_KEY])
        self.assertEqual(len(missions), 1)
        self.assertEqual(missions[0]["label"], "Mission A")
        self.assertEqual(
            missions[0]["citations"],
            [("todo", "item one"), ("deep", "item two")],
        )
        self.assertTrue(missions[0]["monitored"])

    def test_no_marker_is_unmonitored(self):
        sections = plc.split_sections(UNMONITORED_TRACKER)
        missions = plc.extract_missions(sections[plc.PINNED_KEY])
        self.assertEqual(len(missions), 1)
        self.assertFalse(missions[0]["monitored"])
        self.assertEqual(missions[0]["citations"], [])


class TestResolveCitation(unittest.TestCase):
    def test_checked_item_in_home_section_resolves_true(self):
        sections = plc.split_sections(RESOLVED_TRACKER)
        self.assertTrue(plc.resolve_citation("todo", "item one", sections))

    def test_open_item_in_home_section_resolves_false(self):
        sections = plc.split_sections(OPEN_TRACKER)
        self.assertFalse(plc.resolve_citation("todo", "item one", sections))
        self.assertFalse(plc.resolve_citation("deep", "item two", sections))

    def test_item_only_found_in_completed_resolves_true(self):
        # In RESOLVED_TRACKER, "item two" no longer appears under its home
        # Deep Tasks section at all (it moved out) -- only under Completed.
        sections = plc.split_sections(RESOLVED_TRACKER)
        self.assertTrue(plc.resolve_citation("deep", "item two", sections))

    def test_missing_substring_resolves_none(self):
        sections = plc.split_sections(UNKNOWN_CITATION_TRACKER)
        self.assertIsNone(plc.resolve_citation("todo", "item that does not exist", sections))

    def test_unknown_citation_kind_resolves_none(self):
        sections = plc.split_sections(RESOLVED_TRACKER)
        self.assertIsNone(plc.resolve_citation("bogus-kind", "item one", sections))


class TestEvaluateMission(unittest.TestCase):
    def test_all_citations_resolved_is_resolved(self):
        sections = plc.split_sections(RESOLVED_TRACKER)
        missions = plc.extract_missions(sections[plc.PINNED_KEY])
        evaluated = plc.evaluate_mission(missions[0], sections)
        self.assertEqual(evaluated["status"], "resolved")

    def test_any_open_citation_is_open(self):
        sections = plc.split_sections(OPEN_TRACKER)
        missions = plc.extract_missions(sections[plc.PINNED_KEY])
        evaluated = plc.evaluate_mission(missions[0], sections)
        self.assertEqual(evaluated["status"], "open")

    def test_unknown_citation_never_reported_as_resolved(self):
        sections = plc.split_sections(UNKNOWN_CITATION_TRACKER)
        missions = plc.extract_missions(sections[plc.PINNED_KEY])
        evaluated = plc.evaluate_mission(missions[0], sections)
        self.assertEqual(evaluated["status"], "unknown")
        self.assertNotEqual(evaluated["status"], "resolved")

    def test_unmonitored_mission_never_becomes_a_candidate(self):
        sections = plc.split_sections(UNMONITORED_TRACKER)
        missions = plc.extract_missions(sections[plc.PINNED_KEY])
        evaluated = plc.evaluate_mission(missions[0], sections)
        self.assertEqual(evaluated["status"], "unmonitored")


class TestNextMissionCandidate(unittest.TestCase):
    def test_roadmap_doc_first_unchecked_item_wins(self):
        roadmap_path = write_tracker("# Roadmap\n\n- [x] done already\n- [ ] Next big thing\n- [ ] Another\n")
        try:
            sections = plc.split_sections(DEEP_TASKS_FALLBACK_TRACKER)
            candidate = plc.find_next_mission_candidate(sections, roadmap_path=roadmap_path)
            self.assertEqual(candidate["source"], "roadmap")
            self.assertEqual(candidate["candidate"], "Next big thing")
        finally:
            Path(roadmap_path).unlink()

    def test_falls_back_to_highest_priority_deep_task_when_no_roadmap(self):
        sections = plc.split_sections(DEEP_TASKS_FALLBACK_TRACKER)
        candidate = plc.find_next_mission_candidate(sections, roadmap_path=None)
        self.assertEqual(candidate["source"], "deep-tasks")
        self.assertEqual(candidate["priority"], "P0")
        self.assertEqual(candidate["candidate"], "Highest priority candidate")

    def test_promoted_deep_task_is_skipped(self):
        sections = plc.split_sections(DEEP_TASKS_FALLBACK_TRACKER)
        candidate = plc.find_next_mission_candidate(sections, roadmap_path=None)
        self.assertNotEqual(candidate["candidate"], "Already promoted, skip me")

    def test_no_candidate_when_deep_tasks_empty_and_no_roadmap(self):
        sections = plc.split_sections(RESOLVED_TRACKER)
        candidate = plc.find_next_mission_candidate(sections, roadmap_path=None)
        self.assertIsNone(candidate)


class TestRunEndToEnd(unittest.TestCase):
    def test_resolved_tracker_surfaces_candidate(self):
        path = write_tracker(RESOLVED_TRACKER)
        try:
            report = plc.run(path)
            self.assertEqual(report["resolved_count"], 1)
            self.assertIn("next_mission_candidate", report)
        finally:
            Path(path).unlink()

    def test_open_tracker_never_writes_and_reports_zero_resolved(self):
        path = write_tracker(OPEN_TRACKER)
        before = Path(path).read_text(encoding="utf-8")
        try:
            report = plc.run(path)
            after = Path(path).read_text(encoding="utf-8")
            self.assertEqual(report["resolved_count"], 0)
            self.assertNotIn("next_mission_candidate", report)
            self.assertEqual(before, after)  # never writes to the tracker
        finally:
            Path(path).unlink()

    def test_real_world_loop_governance_fixture_is_open_not_resolved(self):
        """Regression fixture modeled on es6kr's own 2026-09-21 pinned mission:
        one TODO citation still `[ ]` must keep the mission from being
        misreported as resolved."""
        tracker = """# Fix Plan

> 📌 Pinned
> - **Loop governance adoption**: in progress <!-- pinned-backing: todo:"loop-verifier PoC Green", todo:"governance remaining 2 types" -->

## TODO

- [ ] [P2:selfable] loop-verifier PoC Green implementation (Red commit done)
  - Update: Green already implemented, PR still DRAFT with open findings.
- [ ] [P2:selfable] governance remaining 2 types port -- not started
"""
        path = write_tracker(tracker)
        try:
            report = plc.run(path)
            self.assertEqual(report["resolved_count"], 0)
            self.assertEqual(report["missions"][0]["status"], "open")
        finally:
            Path(path).unlink()


if __name__ == "__main__":
    unittest.main()
