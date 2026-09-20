#!/usr/bin/env python3
"""
Unit tests for browse_url wiring in plane_create_issue.py (2026-09-16, 3rd
recurrence fix — see failed-attempts.md "Plane 이슈/Intake 보고 시 워크스페이스·
식별자가 포함된 표준 브라우즈 URL 표기 누락"). create.md's Output Schema told
callers to attach the returned `url` verbatim, and every create path built
that `url` in the banned project-UUID-nested form — this is the actual
mechanism behind the repeated mistake, not an isolated reporting slip.

All network calls are mocked (urllib.request.urlopen, subprocess.run).
"""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock
import importlib.util

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

_client_path = SCRIPT_DIR / "plane_client.py"
_client_spec = importlib.util.spec_from_file_location("plane_client", str(_client_path))
plane_client = importlib.util.module_from_spec(_client_spec)
sys.modules["plane_client"] = plane_client
_client_spec.loader.exec_module(plane_client)

_issue_path = SCRIPT_DIR / "plane_create_issue.py"
_issue_spec = importlib.util.spec_from_file_location("plane_create_issue", str(_issue_path))
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


def _routing_urlopen(create_payload, project_payload):
    """A urlopen fake that tells the create POST apart from the identifier GET
    by method, the way the real Plane REST API distinguishes them."""

    def _fake(req, *a, **kw):
        if req.get_method() == "GET":
            return _FakeResponse(project_payload)
        return _FakeResponse(create_payload)

    return _fake


class TestRestApiBrowseUrl(unittest.TestCase):
    def test_create_via_rest_api_includes_browse_url(self):
        fake = _routing_urlopen(
            create_payload={"id": "issue-uuid", "sequence_id": 62},
            project_payload={"identifier": "INFRA"},
        )
        with mock.patch.object(plane_create_issue.urllib.request, "urlopen", fake):
            res = plane_create_issue.create_via_rest_api(dict(BASE_PROFILE), "title", is_intake=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["browse_url"], "https://plane.dgs.ai.kr/dgs/browse/INFRA-62")
        # The raw API url is retained too — some callers may still want it.
        self.assertIn("/projects/", res["url"])

    def test_create_via_rest_api_degrades_to_none_when_identifier_lookup_fails(self):
        def _fake(req, *a, **kw):
            if req.get_method() == "GET":
                raise plane_create_issue.urllib.error.HTTPError(
                    req.full_url, 403, "Forbidden", {}, None
                )
            return _FakeResponse({"id": "issue-uuid", "sequence_id": 62})

        with mock.patch.object(plane_create_issue.urllib.request, "urlopen", _fake):
            res = plane_create_issue.create_via_rest_api(dict(BASE_PROFILE), "title", is_intake=False)
        self.assertTrue(res["success"])
        self.assertIsNone(res["browse_url"])

    def test_intake_create_includes_browse_url(self):
        fake = _routing_urlopen(
            create_payload={"issue": "issue-uuid", "issue_detail": {"id": "issue-uuid", "sequence_id": 176}},
            project_payload={"identifier": "AIAUTO"},
        )
        with mock.patch.object(plane_create_issue.urllib.request, "urlopen", fake):
            res = plane_create_issue.create_via_rest_api(dict(BASE_PROFILE), "title", is_intake=True)
        self.assertTrue(res["success"])
        self.assertEqual(res["browse_url"], "https://plane.dgs.ai.kr/dgs/browse/AIAUTO-176")


class TestK3sFallbackBrowseUrl(unittest.TestCase):
    def test_generated_script_computes_browse_url_from_prj_identifier(self):
        script = plane_create_issue.build_k3s_py_script(
            "dgs", "bd4376d5-d451-4608-8c08-f9fda009f4a6", "https://plane.dgs.ai.kr",
            "title", "desc", is_intake=False,
        )
        self.assertIn('"browse_url": f"https://plane.dgs.ai.kr/dgs/browse/{prj.identifier}-{issue.sequence_id}"', script)
        self.assertIn('"browse_url": f"https://plane.dgs.ai.kr/dgs/browse/{prj.identifier}-{existing.sequence_id}"', script)
        compile(script, "<k3s_py_script>", "exec")  # generated source must still be valid Python


class TestCliOutputPrefersBrowseUrl(unittest.TestCase):
    def test_main_prints_browse_url_when_present(self):
        fake_res = {
            "success": True, "sequence_id": 62, "method": "REST API", "title": "t",
            "url": "https://plane.dgs.ai.kr/dgs/projects/x/issues/y",
            "browse_url": "https://plane.dgs.ai.kr/dgs/browse/INFRA-62",
        }
        with mock.patch.object(plane_create_issue, "create_plane_issue", return_value=fake_res):
            with mock.patch.object(sys, "argv", ["plane_create_issue.py", "--title", "t"]):
                with mock.patch("builtins.print") as mock_print:
                    plane_create_issue.main()
        printed = "\n".join(str(c.args[0]) for c in mock_print.call_args_list)
        self.assertIn("https://plane.dgs.ai.kr/dgs/browse/INFRA-62", printed)
        self.assertNotIn("/projects/x/issues/y", printed)


if __name__ == "__main__":
    unittest.main()
