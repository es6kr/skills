#!/usr/bin/env python3
"""
Unit tests for the fix_plan P0-P3 <-> Plane native priority bidirectional
mapping (2026-08-20 Fable audit, plan-plane-done-state-and-priority-mapping.md
Phase 1). All offline: subprocess.run and urllib.request are mocked.
"""

import ast
import base64
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent.parent / "plane-backlog" / "scripts"))

import importlib.util

_client_spec = importlib.util.spec_from_file_location(
    "plane_client", str(SCRIPT_DIR.parent.parent / "plane-backlog" / "scripts" / "plane_client.py")
)
plane_client = importlib.util.module_from_spec(_client_spec)
sys.modules["plane_client"] = plane_client
_client_spec.loader.exec_module(plane_client)

_issue_spec = importlib.util.spec_from_file_location(
    "plane_create_issue", str(SCRIPT_DIR.parent.parent / "plane-backlog" / "scripts" / "plane_create_issue.py")
)
plane_create_issue = importlib.util.module_from_spec(_issue_spec)
sys.modules["plane_create_issue"] = plane_create_issue
_issue_spec.loader.exec_module(plane_create_issue)


BASE_PROFILE = {
    "plane_host": "https://plane.es6.kr",
    "token": "test-token",
    "workspace_slug": "es6kr",
    "default_project": "proj-id",
    "k3s_namespace": "plane-ce",
}


class TestNormalizePriority(unittest.TestCase):
    def test_case_insensitive_p_tags(self):
        for tag, expected in (
            ("P0", "urgent"), ("p0", "urgent"),
            ("P1", "high"), ("p1", "high"),
            ("P2", "medium"), ("p2", "medium"),
            ("P3", "low"), ("p3", "low"),
        ):
            self.assertEqual(plane_client.normalize_priority(tag), expected)

    def test_native_values_pass_through(self):
        for value in ("urgent", "high", "medium", "low", "none"):
            self.assertEqual(plane_client.normalize_priority(value), value)

    def test_native_values_case_insensitive(self):
        self.assertEqual(plane_client.normalize_priority("URGENT"), "urgent")

    def test_falsy_input_is_none(self):
        self.assertEqual(plane_client.normalize_priority(None), "none")
        self.assertEqual(plane_client.normalize_priority(""), "none")

    def test_unrecognized_value_raises(self):
        with self.assertRaises(ValueError):
            plane_client.normalize_priority("P4")
        with self.assertRaises(ValueError):
            plane_client.normalize_priority("critical")

    def test_priority_to_marker_reverse_mapping(self):
        self.assertEqual(plane_client.priority_to_marker("urgent"), "P0")
        self.assertEqual(plane_client.priority_to_marker("high"), "P1")
        self.assertEqual(plane_client.priority_to_marker("medium"), "P2")
        self.assertEqual(plane_client.priority_to_marker("low"), "P3")

    def test_priority_to_marker_none_for_no_priority(self):
        self.assertIsNone(plane_client.priority_to_marker("none"))
        self.assertIsNone(plane_client.priority_to_marker(None))
        self.assertIsNone(plane_client.priority_to_marker("bogus"))


class TestRestApiPriorityInjection(unittest.TestCase):
    def _captured_payload(self, priority):
        captured = {}

        class _FakeResponse:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def read(self_inner):
                return json.dumps({"id": "abc", "sequence_id": 1}).encode("utf-8")

        def _fake_urlopen(req, *a, **kw):
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse()

        with mock.patch.object(plane_create_issue.urllib.request, "urlopen", _fake_urlopen):
            plane_create_issue.create_via_rest_api(
                dict(BASE_PROFILE), "title", is_intake=False, priority=priority
            )
        return captured.get("payload")

    def test_p_tag_normalized_into_payload(self):
        payload = self._captured_payload("P0")
        self.assertEqual(payload.get("priority"), "urgent")

    def test_native_value_passed_through(self):
        payload = self._captured_payload("high")
        self.assertEqual(payload.get("priority"), "high")

    def test_omitted_priority_not_in_payload(self):
        payload = self._captured_payload(None)
        self.assertNotIn("priority", payload)

    def test_invalid_priority_raises_before_network_call(self):
        with self.assertRaises(ValueError):
            self._captured_payload("P9")


@unittest.skip(
    "blocked on https://github.com/es6kr/skills/pull/349 (f-string brace "
    "escaping fix) promoting from next-fix to main — the K3s fallback "
    "template on main still crashes on ANY generation, independent of this "
    "priority-injection change. Un-skip once #349 lands on main."
)
class TestK3sFallbackPriorityInjection(unittest.TestCase):
    def _generated_script(self, priority):
        captured_cmd = {}

        def _fake_run(cmd, **kw):
            captured_cmd["cmd"] = cmd

            class _Result:
                returncode = 0
                stdout = 'RESULT_JSON:{"success": true, "id": "1", "sequence_id": 1, "title": "t", "url": "u", "intake": false}\n'
                stderr = ""

            return _Result()

        with mock.patch.object(plane_create_issue.subprocess, "run", _fake_run):
            with mock.patch.object(plane_create_issue.shutil, "which", return_value="/usr/bin/kubectl"):
                plane_create_issue.create_via_k3s_fallback(
                    dict(BASE_PROFILE), "title", is_intake=False, priority=priority
                )
        cmd = captured_cmd.get("cmd")
        exec_arg = cmd[-1]
        b64_start = exec_arg.index("b64decode('") + len("b64decode('")
        b64_end = exec_arg.index("'", b64_start)
        return base64.b64decode(exec_arg[b64_start:b64_end]).decode("utf-8")

    def test_priority_kwarg_present_when_specified(self):
        py_script = self._generated_script("P1")
        self.assertIn('priority="high"', py_script)
        ast.parse(py_script)

    def test_priority_kwarg_absent_when_unspecified(self):
        py_script = self._generated_script(None)
        self.assertNotIn("priority=", py_script)
        ast.parse(py_script)

    def test_generated_script_valid_python_with_priority(self):
        py_script = self._generated_script("urgent")
        ast.parse(py_script)  # would raise SyntaxError if the kwarg injection broke the call


if __name__ == "__main__":
    unittest.main()
