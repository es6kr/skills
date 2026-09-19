#!/usr/bin/env python3
"""
Unit tests for PlaneClient.browse_url() (2026-09-16, 3rd recurrence of the
project-UUID-nested-URL reporting mistake — see failed-attempts.md
"Plane 이슈/Intake 보고 시 워크스페이스·식별자가 포함된 표준 브라우즈 URL 표기 누락").

issue_url() returns the internal API-shaped URL
(.../projects/<project-uuid>/issues/<issue-uuid>) and must keep doing so — it
is still useful as a machine-resolvable link. browse_url() is the new
human-facing method and must never regress to that nested-UUID shape.
"""

import sys
import unittest
from pathlib import Path
import importlib.util

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

_client_path = SCRIPT_DIR / "plane_client.py"
_client_spec = importlib.util.spec_from_file_location("plane_client", str(_client_path))
plane_client = importlib.util.module_from_spec(_client_spec)
sys.modules["plane_client"] = plane_client
_client_spec.loader.exec_module(plane_client)


def make_client(host="https://plane.dgs.ai.kr", slug="dgs"):
    client = plane_client.PlaneClient.__new__(plane_client.PlaneClient)
    client.profile = {"plane_host": host, "workspace_slug": slug}
    return client


class TestBrowseUrl(unittest.TestCase):
    def test_browse_url_matches_standard_format(self):
        client = make_client()
        self.assertEqual(
            client.browse_url("INFRA", 62),
            "https://plane.dgs.ai.kr/dgs/browse/INFRA-62",
        )

    def test_browse_url_accepts_int_or_str_sequence_id(self):
        client = make_client()
        self.assertEqual(client.browse_url("DTWEB", 37), client.browse_url("DTWEB", "37"))

    def test_browse_url_never_contains_projects_issues_path(self):
        client = make_client()
        url = client.browse_url("AIAUTO", 176)
        self.assertNotIn("/projects/", url)
        self.assertNotIn("/issues/", url)

    def test_issue_url_still_returns_the_internal_api_shape(self):
        # issue_url() is intentionally unchanged — it is the internal/API URL,
        # not a reporting format. This test pins that so a future edit doesn't
        # silently collapse the two methods into one.
        client = make_client()
        url = client.issue_url("11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222")
        self.assertIn("/projects/11111111-1111-1111-1111-111111111111/", url)
        self.assertIn("/issues/22222222-2222-2222-2222-222222222222", url)


class TestListProjects(unittest.TestCase):
    def test_list_projects_handles_bare_list_response(self):
        client = make_client()
        client.request = lambda path: [{"id": "p1", "identifier": "P1"}]
        projects = client.list_projects()
        self.assertEqual(projects, [{"id": "p1", "identifier": "P1"}])

    def test_list_projects_paginates_cursor(self):
        client = make_client()
        calls = []

        def fake_request(path):
            calls.append(path)
            if "cursor=100:0:0" in path:
                return {
                    "results": [{"id": "p1", "identifier": "P1"}],
                    "next_cursor": "100:1:0",
                    "next_page_results": True,
                }
            return {
                "results": [{"id": "p2", "identifier": "P2"}],
                "next_cursor": None,
                "next_page_results": False,
            }

        client.request = fake_request
        projects = client.list_projects()
        self.assertEqual(len(projects), 2)
        self.assertEqual(projects[0]["identifier"], "P1")
        self.assertEqual(projects[1]["identifier"], "P2")
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()

