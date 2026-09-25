#!/usr/bin/env python3
"""Unit tests for PlaneClient.list_intake_issues() / list_issues(include_intake=...).

Regression coverage for SKILL-37: Plane's plain `issues/` endpoint never
returns issues still sitting in the intake/Triage inbox, so
plane_verify_identifier.py (and anything else checking "does this
identifier exist") got a false negative for anything not yet triaged.
"""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

_client_spec = importlib.util.spec_from_file_location("plane_client", str(SCRIPT_DIR / "plane_client.py"))
plane_client = importlib.util.module_from_spec(_client_spec)
sys.modules["plane_client"] = plane_client
_client_spec.loader.exec_module(plane_client)


def make_client():
    client = plane_client.PlaneClient.__new__(plane_client.PlaneClient)
    client.profile = {"plane_host": "https://plane.example.com", "workspace_slug": "myws"}
    client.cache_path = None
    return client


class TestListIntakeIssues(unittest.TestCase):
    def test_unwraps_issue_detail_and_adds_intake_status(self):
        client = make_client()
        page = {
            "results": [
                {
                    "status": -2,
                    "issue_detail": {"id": "issue-1", "sequence_id": 37, "name": "pending triage"},
                },
                {
                    "status": 1,
                    "issue_detail": {"id": "issue-2", "sequence_id": 38, "name": "already accepted"},
                },
            ],
            "next_cursor": None,
            "next_page_results": False,
        }
        with patch.object(client, "request", return_value=page) as mock_request:
            issues = client.list_intake_issues("proj-1")

        mock_request.assert_called_once()
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0]["id"], "issue-1")
        self.assertEqual(issues[0]["sequence_id"], 37)
        self.assertEqual(issues[0]["intake_status"], -2)
        self.assertEqual(issues[1]["intake_status"], 1)

    def test_entries_without_issue_detail_are_skipped(self):
        client = make_client()
        page = {
            "results": [{"status": -2, "issue_detail": None}],
            "next_cursor": None,
            "next_page_results": False,
        }
        with patch.object(client, "request", return_value=page):
            issues = client.list_intake_issues("proj-1")
        self.assertEqual(issues, [])

    def test_follows_pagination(self):
        client = make_client()
        page1 = {
            "results": [{"status": -2, "issue_detail": {"id": "issue-1", "sequence_id": 1}}],
            "next_cursor": "100:1:0",
            "next_page_results": True,
        }
        page2 = {
            "results": [{"status": -2, "issue_detail": {"id": "issue-2", "sequence_id": 2}}],
            "next_cursor": None,
            "next_page_results": False,
        }
        with patch.object(client, "request", side_effect=[page1, page2]) as mock_request:
            issues = client.list_intake_issues("proj-1")
        self.assertEqual(mock_request.call_count, 2)
        self.assertEqual([i["id"] for i in issues], ["issue-1", "issue-2"])


class TestListIssuesIncludeIntake(unittest.TestCase):
    def test_default_excludes_intake(self):
        client = make_client()
        base_page = {
            "results": [{"id": "issue-1", "sequence_id": 1}],
            "next_cursor": None,
            "next_page_results": False,
        }
        with patch.object(client, "request", return_value=base_page) as mock_request:
            issues = client.list_issues("proj-1", use_cache=False)
        self.assertEqual([i["id"] for i in issues], ["issue-1"])
        # only the issues/ page was fetched — no intake-issues/ round trip.
        mock_request.assert_called_once()

    def test_include_intake_merges_without_duplicating(self):
        client = make_client()
        base_page = {
            "results": [{"id": "issue-1", "sequence_id": 1}],
            "next_cursor": None,
            "next_page_results": False,
        }
        intake_page = {
            "results": [
                # already present in the base list — must not be duplicated
                {"status": 1, "issue_detail": {"id": "issue-1", "sequence_id": 1}},
                # Triage-only — must be added
                {"status": -2, "issue_detail": {"id": "issue-2", "sequence_id": 37}},
            ],
            "next_cursor": None,
            "next_page_results": False,
        }
        with patch.object(client, "request", side_effect=[base_page, intake_page]):
            issues = client.list_issues("proj-1", use_cache=False, include_intake=True)
        self.assertEqual(sorted(i["id"] for i in issues), ["issue-1", "issue-2"])
        self.assertEqual(len(issues), 2)


if __name__ == "__main__":
    unittest.main()
