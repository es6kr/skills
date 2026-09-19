#!/usr/bin/env python3
"""Unit tests for plane_verify_identifier.py.

Covers the identifier/browse-url parsers, the resolve() lookup (against a
fake duck-typed client — no network), and main()'s exit codes for the three
outcomes: resolves+matches (0), does not resolve (1), resolves but the title
doesn't match --expect-title-contains (2).
"""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

spec = importlib.util.spec_from_file_location("plane_verify_identifier", str(SCRIPT_DIR / "plane_verify_identifier.py"))
pvi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pvi)


class FakeClient:
    """Duck-typed stand-in for PlaneClient — no network, no profile."""

    def __init__(self, projects, issues_by_project_id):
        self._projects = projects
        self._issues_by_project_id = issues_by_project_id
        self.profile = {"plane_host": "https://plane.example.com", "workspace_slug": "myws"}

    def list_projects(self):
        return self._projects

    def list_issues(self, project_id):
        return self._issues_by_project_id.get(project_id, [])


class TestParseIdentifier(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(pvi.parse_identifier("ES6KR-128"), ("ES6KR", 128))

    def test_lowercase_normalized_uppercase(self):
        self.assertEqual(pvi.parse_identifier("infra-6"), ("INFRA", 6))

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            pvi.parse_identifier("not-an-identifier")

    def test_missing_number_raises(self):
        with self.assertRaises(ValueError):
            pvi.parse_identifier("ES6KR-")


class TestParseBrowseUrl(unittest.TestCase):
    def test_valid(self):
        url = "https://plane.dgs.ai.kr/dgs/browse/ES6KR-128"
        self.assertEqual(pvi.parse_browse_url(url), ("ES6KR", 128))

    def test_trailing_path_ignored(self):
        url = "https://plane.dgs.ai.kr/dgs/browse/INFRA-6/some-slug-suffix"
        self.assertEqual(pvi.parse_browse_url(url), ("INFRA", 6))

    def test_no_browse_segment_raises(self):
        with self.assertRaises(ValueError):
            pvi.parse_browse_url("https://plane.dgs.ai.kr/dgs/projects/uuid/issues/uuid")


class TestResolve(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient(
            projects=[{"id": "proj-1", "identifier": "ES6KR"}, {"id": "proj-2", "identifier": "INFRA"}],
            issues_by_project_id={
                "proj-1": [
                    {"sequence_id": 128, "name": "hook registry relocation", "state_id": "done"},
                    {"sequence_id": 129, "name": "unrelated other issue", "state_id": "todo"},
                ],
            },
        )

    def test_finds_project_and_issue(self):
        project, issue = pvi.resolve(self.client, "ES6KR", 128)
        self.assertEqual(project["id"], "proj-1")
        self.assertEqual(issue["name"], "hook registry relocation")

    def test_unknown_project_code_raises(self):
        with self.assertRaisesRegex(LookupError, "no project with identifier"):
            pvi.resolve(self.client, "NOPE", 1)

    def test_unknown_sequence_id_raises(self):
        with self.assertRaisesRegex(LookupError, "does not exist"):
            pvi.resolve(self.client, "ES6KR", 999)


class TestMain(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient(
            projects=[{"id": "proj-1", "identifier": "ES6KR"}],
            issues_by_project_id={
                "proj-1": [{"sequence_id": 128, "name": "hook registry relocation", "state_id": "done"}],
            },
        )

    def test_resolves_and_title_matches_exit_0(self):
        with patch.object(pvi, "PlaneClient", return_value=self.client):
            rc = pvi.main(["ES6KR-128", "--expect-title-contains", "hook registry"])
        self.assertEqual(rc, 0)

    def test_resolves_without_expectation_exit_0(self):
        with patch.object(pvi, "PlaneClient", return_value=self.client):
            rc = pvi.main(["ES6KR-128"])
        self.assertEqual(rc, 0)

    def test_unresolvable_identifier_exit_1(self):
        with patch.object(pvi, "PlaneClient", return_value=self.client):
            rc = pvi.main(["ES6KR-999"])
        self.assertEqual(rc, 1)

    def test_title_mismatch_exit_2(self):
        # This is the exact class of bug the script exists to catch: a wrong
        # key is cited, and the real title has nothing to do with what the
        # caller expected.
        with patch.object(pvi, "PlaneClient", return_value=self.client):
            rc = pvi.main(["ES6KR-128", "--expect-title-contains", "totally different topic"])
        self.assertEqual(rc, 2)

    def test_browse_url_input_resolves_same_as_bare_identifier(self):
        with patch.object(pvi, "PlaneClient", return_value=self.client):
            rc = pvi.main(["--browse-url", "https://plane.example.com/myws/browse/ES6KR-128"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
