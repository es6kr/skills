#!/usr/bin/env python3
"""Unit tests for plane_create_entity.py's Phase 1 idempotency guard
(rest_search_exact_title / create_via_rest_api's pre-POST check).

Regression coverage for the fix_plan.md "Plane 백로그 및 산출물 등록 시
중복 검사" item — the REST path (`create_via_rest_api`) had no exact-title
guard while the K3s Django-shell path already did, so the same title could
be created twice depending on which path a caller happened to take.
"""

import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

_spec = importlib.util.spec_from_file_location("plane_create_entity", str(SCRIPT_DIR / "plane_create_entity.py"))
plane_create_entity = importlib.util.module_from_spec(_spec)
sys.modules["plane_create_entity"] = plane_create_entity
_spec.loader.exec_module(plane_create_entity)


class FakeResponse:
    """Minimal stand-in for the object `urllib.request.urlopen()` returns,
    usable as a context manager (`with urlopen(req) as resp:`)."""

    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")
        self.status = 200

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def paged_urlopen(pages):
    """Return a side_effect function serving `pages` in order, one per call
    (mirrors the cursor-pagination loop in rest_search_exact_title)."""
    it = iter(pages)

    def _urlopen(req, timeout=None):
        return FakeResponse(next(it))

    return _urlopen


class TestRestSearchExactTitle(unittest.TestCase):
    def test_finds_match_on_first_page(self):
        page = {
            "results": [
                {"id": "issue-1", "name": "unrelated title", "sequence_id": 10},
                {"id": "issue-2", "name": "exact match", "sequence_id": 11},
            ],
            "next_cursor": None,
            "next_page_results": False,
        }
        with patch("urllib.request.urlopen", side_effect=paged_urlopen([page])):
            found = plane_create_entity.rest_search_exact_title(
                "https://plane.example.com", "myws", "proj-1", "tok", "exact match"
            )
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], "issue-2")

    def test_finds_match_across_pagination(self):
        page1 = {
            "results": [{"id": "issue-1", "name": "page one item", "sequence_id": 1}],
            "next_cursor": "100:1:0",
            "next_page_results": True,
        }
        page2 = {
            "results": [{"id": "issue-2", "name": "page two match", "sequence_id": 2}],
            "next_cursor": None,
            "next_page_results": False,
        }
        with patch("urllib.request.urlopen", side_effect=paged_urlopen([page1, page2])):
            found = plane_create_entity.rest_search_exact_title(
                "https://plane.example.com", "myws", "proj-1", "tok", "page two match"
            )
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], "issue-2")

    def test_no_match_returns_none(self):
        page = {
            "results": [{"id": "issue-1", "name": "something else", "sequence_id": 1}],
            "next_cursor": None,
            "next_page_results": False,
        }
        with patch("urllib.request.urlopen", side_effect=paged_urlopen([page])):
            found = plane_create_entity.rest_search_exact_title(
                "https://plane.example.com", "myws", "proj-1", "tok", "does not exist"
            )
        self.assertIsNone(found)

    def test_fetch_error_returns_none_not_raise(self):
        """A network/API failure must degrade to 'no match found', not
        propagate — idempotency is a best-effort guard, never a hard gate
        that could block issue creation on a transient error."""
        with patch("urllib.request.urlopen", side_effect=OSError("boom")):
            found = plane_create_entity.rest_search_exact_title(
                "https://plane.example.com", "myws", "proj-1", "tok", "anything"
            )
        self.assertIsNone(found)


class TestCreateViaRestApiIdempotency(unittest.TestCase):
    def _profile(self):
        return {
            "plane_host": "https://plane.example.com",
            "token": "tok",
            "workspace_slug": "myws",
            "default_project": "proj-1",
        }

    def test_existing_title_skips_post_and_returns_idempotency_guard_result(self):
        existing = {"id": "issue-existing", "name": "dup title", "sequence_id": 42}
        with patch.object(plane_create_entity, "rest_search_exact_title", return_value=existing) as mock_search, \
             patch("urllib.request.urlopen") as mock_urlopen:
            result = plane_create_entity.create_via_rest_api(self._profile(), "dup title")

        mock_search.assert_called_once()
        mock_urlopen.assert_not_called()  # no POST should happen on a duplicate
        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "Existing (Idempotency Guard)")
        self.assertEqual(result["id"], "issue-existing")
        self.assertEqual(result["sequence_id"], 42)
        self.assertIn("issue-existing", result["url"])

    def test_no_existing_title_proceeds_to_create(self):
        create_response = {"id": "new-issue", "sequence_id": 99}

        def _urlopen(req, timeout=None):
            return FakeResponse(create_response)

        with patch.object(plane_create_entity, "rest_search_exact_title", return_value=None) as mock_search, \
             patch("urllib.request.urlopen", side_effect=_urlopen) as mock_urlopen:
            result = plane_create_entity.create_via_rest_api(
                self._profile(), "brand new title", is_intake=False
            )

        mock_search.assert_called_once()
        mock_urlopen.assert_called_once()  # the create POST did happen
        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "REST API")
        self.assertEqual(result["id"], "new-issue")


if __name__ == "__main__":
    unittest.main()
