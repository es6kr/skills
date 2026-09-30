#!/usr/bin/env python3
"""Unit tests for plane_create_issue.py's Phase 1 idempotency guard
(rest_search_exact_title / create_via_rest_api's pre-POST check).

Regression coverage for the fix_plan.md "Plane 백로그 및 산출물 등록 시
중복 검사" item. This file's `create_via_rest_api` defaults to `is_intake=True`,
which creates issues *only* via the intake endpoint — so the guard must check
both `issues/` (regular, triaged) and `intake-issues/` (Triage) lists, or it
would miss the common case entirely.

All network calls are mocked (urllib.request.urlopen).
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

_client_spec = importlib.util.spec_from_file_location("plane_client", str(SCRIPT_DIR / "plane_client.py"))
plane_client = importlib.util.module_from_spec(_client_spec)
sys.modules["plane_client"] = plane_client
_client_spec.loader.exec_module(plane_client)

_issue_spec = importlib.util.spec_from_file_location("plane_create_issue", str(SCRIPT_DIR / "plane_create_issue.py"))
plane_create_issue = importlib.util.module_from_spec(_issue_spec)
sys.modules["plane_create_issue"] = plane_create_issue
_issue_spec.loader.exec_module(plane_create_issue)


BASE_PROFILE = {
    "plane_host": "https://plane.dgs.ai.kr",
    "token": "test-token",
    "workspace_slug": "dgs",
    "default_project": "bd4376d5-d451-4608-8c08-f9fda009f4a6",
}


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def _empty_list_page():
    return {"results": [], "next_cursor": None, "next_page_results": False}


class TestFetchPagesForExactTitle(unittest.TestCase):
    def test_finds_match_in_plain_results(self):
        page = {
            "results": [{"id": "i1", "name": "other"}, {"id": "i2", "name": "target"}],
            "next_cursor": None,
            "next_page_results": False,
        }
        with mock.patch.object(plane_create_issue.urllib.request, "urlopen", lambda req, **kw: _FakeResponse(page)):
            found = plane_create_issue._fetch_pages_for_exact_title(
                "https://plane.example.com", "ws", "proj-1", "tok", "target", "issues"
            )
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], "i2")

    def test_unwraps_issue_detail_for_intake_list(self):
        page = {
            "results": [
                {"status": -2, "issue_detail": {"id": "i1", "name": "pending target"}},
            ],
            "next_cursor": None,
            "next_page_results": False,
        }
        with mock.patch.object(plane_create_issue.urllib.request, "urlopen", lambda req, **kw: _FakeResponse(page)):
            found = plane_create_issue._fetch_pages_for_exact_title(
                "https://plane.example.com", "ws", "proj-1", "tok", "pending target",
                "intake-issues", unwrap_issue_detail=True,
            )
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], "i1")

    def test_error_degrades_to_none(self):
        def _boom(req, **kw):
            raise OSError("network down")

        with mock.patch.object(plane_create_issue.urllib.request, "urlopen", _boom):
            found = plane_create_issue._fetch_pages_for_exact_title(
                "https://plane.example.com", "ws", "proj-1", "tok", "anything", "issues"
            )
        self.assertIsNone(found)


class TestRestSearchExactTitleChecksBothLists(unittest.TestCase):
    def test_falls_back_to_intake_list_when_issues_list_has_no_match(self):
        calls = []

        def _fake(req, **kw):
            calls.append(req.full_url)
            if "/intake-issues/" in req.full_url:
                return _FakeResponse({
                    "results": [{"status": -2, "issue_detail": {"id": "intake-1", "name": "dup"}}],
                    "next_cursor": None,
                    "next_page_results": False,
                })
            return _FakeResponse(_empty_list_page())

        with mock.patch.object(plane_create_issue.urllib.request, "urlopen", _fake):
            found = plane_create_issue.rest_search_exact_title(
                "https://plane.example.com", "ws", "proj-1", "tok", "dup"
            )
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], "intake-1")
        self.assertTrue(any("/issues/" in u and "/intake-issues/" not in u for u in calls))
        self.assertTrue(any("/intake-issues/" in u for u in calls))


class TestCreateViaRestApiIdempotency(unittest.TestCase):
    def test_existing_title_skips_creation_intake_default(self):
        def _fake(req, **kw):
            if "/intake-issues/" in req.full_url and req.get_method() == "GET":
                return _FakeResponse({
                    "results": [{"status": -2, "issue_detail": {"id": "existing-1", "name": "dup title", "sequence_id": 7}}],
                    "next_cursor": None,
                    "next_page_results": False,
                })
            if req.get_method() == "GET":
                return _FakeResponse(_empty_list_page())
            self.fail(f"unexpected POST during a duplicate-title create: {req.full_url}")

        with mock.patch.object(plane_create_issue.urllib.request, "urlopen", _fake):
            res = plane_create_issue.create_via_rest_api(dict(BASE_PROFILE), "dup title")

        self.assertTrue(res["success"])
        self.assertEqual(res["method"], "Existing (Idempotency Guard)")
        self.assertEqual(res["id"], "existing-1")
        self.assertEqual(res["sequence_id"], 7)

    def test_no_existing_title_proceeds_to_intake_post(self):
        posts = []

        def _fake(req, **kw):
            if req.get_method() == "GET" and "/projects/" in req.full_url and req.full_url.rstrip("/").endswith(BASE_PROFILE["default_project"]):
                return _FakeResponse({"identifier": "INFRA"})
            if req.get_method() == "GET":
                return _FakeResponse(_empty_list_page())
            posts.append(req.full_url)
            return _FakeResponse({"issue": "new-1", "issue_detail": {"id": "new-1", "sequence_id": 99}})

        with mock.patch.object(plane_create_issue.urllib.request, "urlopen", _fake):
            res = plane_create_issue.create_via_rest_api(dict(BASE_PROFILE), "brand new title")

        self.assertEqual(len(posts), 1)  # the intake create POST did happen
        self.assertTrue(res["success"])
        self.assertEqual(res["method"], "REST API (intake)")


if __name__ == "__main__":
    unittest.main()
