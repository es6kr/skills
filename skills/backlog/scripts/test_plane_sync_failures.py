#!/usr/bin/env python3
"""Synthetic transport failures must not leak input or certify a successful sync."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

SOURCE = Path(__file__).with_name("plane_sync.py")
SPEC = importlib.util.spec_from_file_location("fixture_plane_sync", SOURCE)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)
PROJECT = "11111111-1111-1111-1111-111111111111"
OTHER_PROJECT = "99999999-9999-9999-9999-999999999999"
FIRST = "22222222-2222-2222-2222-222222222222"
SECOND = "66666666-6666-6666-6666-666666666666"
STATE = "55555555-5555-5555-5555-555555555555"
SENTINEL = "SYNTHETIC_REQUEST_INPUT_MUST_NOT_APPEAR"


def profile():
    return {"workspace_name": "fixture", "plane_host": "https://plane.example.invalid",
            "plane_token": "fixture-key", "plane_token_env": "FIXTURE_PLANE_TOKEN"}


def index_line(number=1, issue=FIRST, marker=" ", browse=False):
    location = f"browse/FIXTURE-{number}" if browse else f"projects/{PROJECT}/issues/{issue}"
    return f"- [{marker}] [FIXTURE-{number}] synthetic issue -> Plane (https://plane.example.invalid/fixture/{location})"


class TestSafeTransportDiagnostics(unittest.TestCase):
    def test_header_exception_does_not_return_credential_or_request_contents(self):
        with patch.object(sync, "_build_opener", side_effect=ValueError(SENTINEL)):
            result = sync.make_plane_request(profile(), "workspaces/fixture/projects/")
        self.assertIn("error", result)
        self.assertFalse(SENTINEL in json.dumps(result), "returned diagnostics must omit raw exception text")

    def test_http_status_is_retained_without_echoing_reason_or_response_body(self):
        error = urllib.error.HTTPError("https://plane.example.invalid/", 403, SENTINEL, {}, io.BytesIO(SENTINEL.encode()))
        with patch.object(sync, "_build_opener", side_effect=error):
            result = sync.make_plane_request(profile(), "workspaces/fixture/projects/")
        self.assertIn("error", result)
        self.assertFalse(SENTINEL in json.dumps(result), "HTTP reason/body must not leak")
        self.assertIn("403", str(result["error"]))

    def test_crlf_environment_value_is_rejected_before_opener_creation(self):
        selected = profile()
        selected["plane_token"] = "fixture-key\r\nInjected: fixture"
        with patch.object(sync, "_build_opener") as opener:
            result = sync.make_plane_request(selected, "workspaces/fixture/projects/")
        self.assertIn("error", result)
        self.assertEqual(opener.call_count, 0, "invalid headers must not reach a transport")
        self.assertFalse("fixture-key" in json.dumps(result))

    def test_malformed_endpoint_returns_safe_error_instead_of_escaping(self):
        selected = profile()
        selected["plane_host"] = "https://[" + SENTINEL
        try:
            result = sync.make_plane_request(selected, "workspaces/fixture/projects/")
        except Exception as error:
            self.fail("malformed endpoint escaped as " + type(error).__name__)
        self.assertIn("error", result)
        self.assertFalse(SENTINEL in json.dumps(result))


class TestSyncFailurePropagation(unittest.TestCase):
    def execute(self, lines, failure=None, push_done=False, no_token=False):
        calls = []
        wrote_done = False
        selected = profile()
        if no_token:
            selected["plane_token"] = ""
        selected_before = dict(selected)

        def request(_profile, path, method="GET", data=None):
            nonlocal wrote_done
            calls.append((method, path))
            if method == "PATCH":
                wrote_done = failure != "patch-error"
                return {"error": SENTINEL} if failure == "patch-error" else {"id": FIRST, "state": STATE}
            if path == "workspaces/fixture/projects/":
                if failure == "projects":
                    return {"error": SENTINEL}
                if failure == "unknown-project":
                    return {"results": [], "next_page_results": False}
                return {"results": [{"id": PROJECT, "identifier": "FIXTURE"}], "next_page_results": False}
            if "/issues/?" in path:
                if "cursor=" in path and failure == "pagination":
                    return {"error": SENTINEL}
                listing = {"results": [{"id": FIRST, "sequence_id": 1}], "next_page_results": False}
                if failure == "unknown-sequence":
                    listing["results"] = []
                if failure == "pagination":
                    listing.update(next_page_results=True, next_cursor="100:1:0")
                if failure == "missing-cursor":
                    listing.update(next_page_results=True, next_cursor=None)
                if failure == "page-cap":
                    listing.update(next_page_results=True, next_cursor="100:1:0")
                return listing
            if path.endswith("states/"):
                if failure == "late-project-state" and OTHER_PROJECT in path:
                    return {"error": SENTINEL}
                return {"results": [{"id": STATE, "group": "completed"}]}
            if f"states/{STATE}/" in path:
                if failure == "state":
                    return {"error": SENTINEL}
                if failure == "missing-group":
                    return {"id": STATE}
                if failure == "cancelled-before-push":
                    return {"id": STATE, "group": "completed" if wrote_done else "cancelled"}
                return {"id": STATE, "group": "started" if push_done or failure == "unchanged" else "completed"}
            if "/issues/" in path:
                if failure == "issue" or (failure in ("mixed", "push-read") and SECOND in path):
                    return {"error": SENTINEL}
                if failure == "missing-state":
                    return {"id": FIRST, "priority": "medium"}
                return {"id": FIRST, "state": STATE, "priority": "medium"}
            return {"error": "unexpected synthetic request"}

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "fixture-plan.md"
            original = ("\n".join(lines) + "\n").encode("utf-8")
            target.write_bytes(original)
            output = io.StringIO()
            with patch.object(sync, "make_plane_request", side_effect=request), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                status = sync.sync_checklist_with_plane(target, selected, push_done=push_done)
            final = target.read_bytes()
            self.assertFalse(target.with_name(target.name + ".tmp").exists())
        self.assertEqual(selected, selected_before, "run diagnostics must not mutate caller profile")
        return status, output.getvalue(), original, final, calls

    def assert_failed_without_write(self, result):
        status, output, original, final, _ = result
        self.assertEqual(final, original, "an incomplete read must not publish a partial local snapshot")
        self.assertIsInstance(status, int, "sync must return a process-visible failure status")
        self.assertNotEqual(status, 0)
        self.assertFalse("no changes" in output.lower(), "API failure must not be reported as a successful no-op")

    def test_project_listing_failure_is_not_successful_zero_changes(self):
        self.assert_failed_without_write(self.execute([index_line(browse=True)], "projects"))

    def test_issue_read_failure_is_not_successful_zero_changes(self):
        self.assert_failed_without_write(self.execute([index_line()], "issue"))

    def test_unresolved_project_fails_preflight_instead_of_silent_noop(self):
        self.assert_failed_without_write(self.execute([index_line(browse=True)], "unknown-project"))

    def test_unresolved_issue_fails_preflight_instead_of_silent_noop(self):
        self.assert_failed_without_write(self.execute([index_line(browse=True)], "unknown-sequence"))

    def test_state_lookup_failure_is_not_successful_zero_changes(self):
        self.assert_failed_without_write(self.execute([index_line()], "state"))

    def test_later_page_failure_does_not_certify_partial_listing(self):
        self.assert_failed_without_write(self.execute([index_line(browse=True)], "pagination"))

    def test_missing_cursor_is_not_a_complete_listing(self):
        self.assert_failed_without_write(self.execute([index_line(browse=True)], "missing-cursor"))

    def test_page_limit_is_not_a_complete_listing(self):
        with patch.object(sync, "MAX_ISSUE_PAGES", 1):
            self.assert_failed_without_write(self.execute([index_line(browse=True)], "page-cap"))

    def test_missing_issue_state_fails_verification(self):
        self.assert_failed_without_write(self.execute([index_line()], "missing-state"))

    def test_missing_state_group_fails_verification(self):
        self.assert_failed_without_write(self.execute([index_line()], "missing-group"))

    def test_mixed_success_and_failure_preserves_whole_tracker(self):
        self.assert_failed_without_write(self.execute([index_line(), index_line(2, SECOND)], "mixed"))

    def test_failed_push_preflight_never_starts_patch_operations(self):
        result = self.execute([index_line(marker="x"), index_line(2, SECOND, marker="x")], "push-read", push_done=True)
        self.assertFalse(any(method != "GET" for method, _ in result[4]), "read failures must gate all writes")
        self.assert_failed_without_write(result)

    def test_patch_failure_diagnostics_do_not_echo_request_input(self):
        result = self.execute([index_line(marker="x")], "patch-error", push_done=True)
        self.assertTrue(any(method == "PATCH" for method, _ in result[4]), "fixture must exercise the PATCH boundary")
        self.assertFalse(SENTINEL in result[1], "sync diagnostics must omit raw transport errors")
        self.assert_failed_without_write(result)

    def test_all_project_state_reads_finish_before_any_patch(self):
        other = index_line(2, SECOND, marker="x").replace(PROJECT, OTHER_PROJECT)
        result = self.execute([index_line(marker="x"), other], "late-project-state", push_done=True)
        self.assertFalse(any(method != "GET" for method, _ in result[4]), "late project-state failure must prevent the first PATCH")
        self.assert_failed_without_write(result)

    def test_successful_unchanged_read_still_reports_honest_noop(self):
        status, output, original, final, _ = self.execute([index_line()], "unchanged")
        self.assertIn(status, (None, 0))
        self.assertEqual(final, original)
        self.assertIn("no changes", output.lower())

    def test_successful_done_push_does_not_restore_preflight_cancelled_marker(self):
        status, _, original, final, calls = self.execute([index_line(marker="x")], "cancelled-before-push", push_done=True)
        self.assertEqual(status, 0)
        self.assertTrue(any(method == "PATCH" for method, _ in calls))
        self.assertEqual(final, original, "successful Done transition must not be overwritten by a stale Cancelled projection")

    def test_unconfigured_token_remains_explicit_offline_skip(self):
        status, output, original, final, calls = self.execute([index_line()], no_token=True)
        self.assertIn(status, (None, 0))
        self.assertEqual(calls, [])
        self.assertEqual(final, original)
        self.assertIn("offline", output.lower())
        self.assertNotIn("no changes", output.lower())

    def test_successful_completed_read_can_still_update_marker(self):
        status, output, _, final, _ = self.execute([index_line()])
        self.assertIn(status, (None, 0))
        self.assertIn(b"- [x] [FIXTURE-1]", final)
        self.assertNotIn("failed", output.lower())

    def test_cli_invalid_cache_returns_failure_without_false_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "fixture-cache.txt"
            cache.write_text("# synthetic cache without a value\n", encoding="utf-8")
            target = root / "fixture-plan.md"
            target.write_text(index_line(browse=True) + "\n", encoding="utf-8")
            original = target.read_bytes()
            config = root / "fixture-config.json"
            config.write_text(json.dumps({"profiles": {"fixture": {
                "workspace_name": "fixture", "plane_host": "https://plane.example.invalid",
                "plane_token_env": "FIXTURE_PLANE_TOKEN", "token_file": str(cache),
            }}}), encoding="utf-8")
            env = {k: v for k, v in os.environ.items() if "PLANE" not in k}
            env["AGENT_WORKSPACE_CONFIG"] = str(config)
            result = subprocess.run([sys.executable, "-B", str(SOURCE), "--workspace", "fixture", "--fix-plan", str(target), "--dry-run"], env=env, capture_output=True, text=True, timeout=15)
            output = result.stdout + result.stderr
            self.assertNotIn("Traceback", output)
            self.assertNotIn("SyntaxError", output)
            self.assertEqual(target.read_bytes(), original)
            self.assertNotEqual(result.returncode, 0, "real CLI must propagate authentication-input failure")
            self.assertNotIn("no changes", output.lower())


if __name__ == "__main__":
    unittest.main()
