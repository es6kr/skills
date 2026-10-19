#!/usr/bin/env python3
"""
Browse-URL index lines for plane_sync.py.

Trackers link Plane issues with the canonical browse URL
(https://<host>/<workspace>/browse/<IDENT>-<SEQ>), not the
projects/<uuid>/issues/<uuid> form. Before this test file, every browse-URL
line was skipped by parse_index_lines(), so a live --push-done dry-run
reported "0 pending" even with freshly completed local items.
"""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location("plane_sync", str(SCRIPT_DIR / "plane_sync.py"))
plane_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plane_sync)

PROJECT_ID = "7e57ca1e-0000-0000-0000-000000000001"
ISSUE_ID = "a1b2c3d4-0000-0000-0000-000000000061"
STATE_ID = "55555555-5555-5555-5555-555555555555"

BROWSE_LINE = (
    "- [x] [SKILL-61] some title → Plane "
    "(https://plane.example.com/myws/browse/SKILL-61)"
)


def _profile():
    return {"plane_host": "https://plane.example.com", "plane_token": "tok"}


def _listing(path, *a, **kw):
    """Fake make_plane_request for the project + issue listing calls."""
    if path.rstrip("/") == "workspaces/myws/projects":
        return {"results": [{"identifier": "SKILL", "id": PROJECT_ID}],
                "next_page_results": False}
    if path.startswith(f"workspaces/myws/projects/{PROJECT_ID}/issues"):
        return {"results": [{"sequence_id": 60, "id": "other"},
                            {"sequence_id": 61, "id": ISSUE_ID}],
                "next_page_results": False}
    return {"error": f"unexpected path {path}"}


class TestParseBrowseLines(unittest.TestCase):
    def test_browse_url_line_is_parsed(self):
        matches = plane_sync.parse_index_lines([BROWSE_LINE])
        self.assertEqual(len(matches), 1)
        um = matches[0]["url_match"]
        self.assertEqual(um["workspace"], "myws")
        self.assertEqual(um["ident"], "SKILL-61")

    def test_identifier_with_digit_is_parsed(self):
        # Project identifiers may contain digits (e.g. ES6KR); [A-Z]+ missed them.
        line = BROWSE_LINE.replace("SKILL-61", "ES6KR-178")
        matches = plane_sync.parse_index_lines([line])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["match"].group("ident"), "ES6KR-178")

    def test_priority_prefix_before_ident_is_tolerated(self):
        line = BROWSE_LINE.replace("[x] [SKILL-61]", "[x] (P2) [SKILL-61]")
        matches = plane_sync.parse_index_lines([line])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["match"].group("ident"), "SKILL-61")


class TestBrowseResolution(unittest.TestCase):
    def test_compute_updates_resolves_browse_line(self):
        line = BROWSE_LINE.replace("[x]", "[ ]")
        with patch.object(plane_sync, "make_plane_request", side_effect=_listing), \
             patch.object(plane_sync, "fetch_issue_state",
                          side_effect=lambda p, w, proj, iss: {"state": STATE_ID}
                          if (proj, iss) == (PROJECT_ID, ISSUE_ID) else {"error": "x"}), \
             patch.object(plane_sync, "fetch_state_group", return_value={"group": "completed"}):
            updates = plane_sync.compute_updates([line], _profile())
        self.assertEqual(len(updates), 1)
        self.assertIn("[x]", updates[0]["new"])

    def test_unknown_sequence_is_skipped_not_guessed(self):
        # Exact (project identifier, sequence_id) match only -- never fall back
        # to "first search result" (prior audit Major #1).
        line = BROWSE_LINE.replace("[x]", "[ ]").replace("SKILL-61", "SKILL-999")
        with patch.object(plane_sync, "make_plane_request", side_effect=_listing), \
             patch.object(plane_sync, "fetch_issue_state", return_value={"state": STATE_ID}), \
             patch.object(plane_sync, "fetch_state_group", return_value={"group": "completed"}):
            updates = plane_sync.compute_updates([line], _profile())
        self.assertEqual(updates, [])

    def test_push_done_queues_resolved_browse_line(self):
        with patch.object(plane_sync, "make_plane_request", side_effect=_listing), \
             patch.object(plane_sync, "fetch_issue_state", return_value={"state": STATE_ID}), \
             patch.object(plane_sync, "fetch_state_group", return_value={"group": "started"}):
            queued = plane_sync.compute_local_to_plane_updates([BROWSE_LINE], _profile())
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["project"], PROJECT_ID)
        self.assertEqual(queued[0]["issue"], ISSUE_ID)

    def test_listing_called_once_per_project(self):
        lines = [BROWSE_LINE, BROWSE_LINE.replace("SKILL-61", "SKILL-60")]
        with patch.object(plane_sync, "make_plane_request", side_effect=_listing) as req, \
             patch.object(plane_sync, "fetch_issue_state", return_value={"state": STATE_ID}), \
             patch.object(plane_sync, "fetch_state_group", return_value={"group": "started"}):
            plane_sync.compute_local_to_plane_updates(lines, _profile())
        issue_list_calls = [c for c in req.call_args_list if "/issues" in c.args[0]]
        self.assertEqual(len(issue_list_calls), 1)


if __name__ == "__main__":
    unittest.main()
