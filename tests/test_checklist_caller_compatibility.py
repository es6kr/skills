"""Offline caller compatibility; no hook installation or tracker mutation."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def resolve_runtime(variable, command):
    if variable in os.environ:
        return os.environ[variable]
    executable = shutil.which(command)
    if executable is None:
        raise RuntimeError(f"{command} runtime is required for caller compatibility tests")
    return executable


class RuntimeSelectionCompatibility(unittest.TestCase):
    def test_absent_override_uses_the_discovered_executable(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch("shutil.which", return_value="discovered-runtime") as locate:
            self.assertEqual(resolve_runtime("CHECKLIST_TEST_NODE", "node"), "discovered-runtime")
            locate.assert_called_once_with("node")

    def test_explicit_override_preserves_its_literal_value(self):
        for value in ("", "runtime with spaces"):
            with self.subTest(value=value), \
                    mock.patch.dict(os.environ, {"CHECKLIST_TEST_NODE": value}, clear=True), \
                    mock.patch("shutil.which") as locate:
                self.assertEqual(resolve_runtime("CHECKLIST_TEST_NODE", "node"), value)
                locate.assert_not_called()

    def test_missing_executable_fails_instead_of_skipping(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch("shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "node runtime is required"):
                resolve_runtime("CHECKLIST_TEST_NODE", "node")


class SessionCallerCompatibility(unittest.TestCase):
    def run_hook(self, backend, prompt, session_id="11111111-2222-4333-8444-555555555555"):
        relative = "skills/session/resources/session-id-inject." + backend
        if backend == "js":
            command = [resolve_runtime("CHECKLIST_TEST_NODE", "node"), str(ROOT / relative)]
        else:
            command = [resolve_runtime("CHECKLIST_TEST_BASH", "bash"), str(ROOT / relative)]
        payload = {"session_id": session_id, "transcript_path": "", "prompt": prompt}
        result = subprocess.run(command, input=json.dumps(payload).encode("utf-8"),
                                capture_output=True, timeout=15, env=dict(os.environ))
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        return result.stdout.decode("utf-8")

    def test_canonical_and_qualified_prompts_receive_real_session_context(self):
        for backend in ("js", "sh"):
            for prompt in ("/checklist", "/checklist --pm", "/dgs:checklist update"):
                with self.subTest(backend=backend, prompt=prompt):
                    self.assertIn("11111111-2222-4333-8444-555555555555",
                                  self.run_hook(backend, prompt))

    def test_legacy_and_session_commands_keep_context(self):
        for backend in ("js", "sh"):
            for prompt in ("/fix-plan --pm", "/session id"):
                with self.subTest(backend=backend, prompt=prompt):
                    self.assertIn("11111111-2222-4333-8444-555555555555",
                                  self.run_hook(backend, prompt))

    def test_other_commands_and_ralph_topic_are_not_reinterpreted(self):
        for backend in ("js", "sh"):
            for prompt in ("/checklisting", "/checklist-other", "/ralph fix-plan", "ordinary text"):
                with self.subTest(backend=backend, prompt=prompt):
                    self.assertEqual(self.run_hook(backend, prompt), "")

    def test_missing_session_never_manufactures_context(self):
        for backend in ("js", "sh"):
            with self.subTest(backend=backend):
                self.assertEqual(self.run_hook(backend, "/checklist", session_id=""), "")


class WorkflowRegistrationCompatibility(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = ROOT / "skills/wip/resources/block-wip-register-before-execute.py"
        spec = importlib.util.spec_from_file_location("caller_wip_guard", path)
        self.guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.guard)

    def missing_registration(self, prompt, registered=False):
        path = Path(self.temp.name) / "synthetic.jsonl"
        events = [{"type": "user", "message": {"role": "user", "content": prompt}}]
        if registered:
            events.append({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "TaskCreate", "input": {"subject": "fixture"}}
            ]}})
        path.write_bytes(("\n".join(json.dumps(x) for x in events) + "\n").encode("utf-8"))
        return self.guard.was_workflow_or_registration_without_followup(str(path), r"TaskCreate|TodoWrite")

    def test_checklist_and_qualified_commands_require_registration(self):
        for prompt in ("/checklist --pm", "/dgs:checklist update", "<command-name>/dgs:checklist</command-name>"):
            with self.subTest(prompt=prompt):
                self.assertTrue(self.missing_registration(prompt))

    def test_legacy_still_requires_registration(self):
        self.assertTrue(self.missing_registration("/fix-plan --pm"))

    def test_completed_registration_and_unrelated_commands_are_allowed(self):
        self.assertFalse(self.missing_registration("/checklist update", registered=True))
        for prompt in ("/checklisting", "/checklist-other", "/ralph fix-plan", "ordinary text"):
            with self.subTest(prompt=prompt):
                self.assertFalse(self.missing_registration(prompt))


class CallerGuidanceCompatibility(unittest.TestCase):
    def test_backlog_uses_the_resolved_owner_not_the_old_repository_layout(self):
        text = (ROOT / "skills/backlog/record.md").read_text(encoding="utf-8")
        self.assertNotIn("python skills/fix-plan/scripts/", text)
        self.assertIn("resolved-checklist-root", text)
        self.assertIn("update_item.py", text)
        self.assertIn("add_item.py", text)

    def test_next_knows_both_names_without_rewriting_ralph_topic(self):
        text = (ROOT / "skills/next/ask-gates.md").read_text(encoding="utf-8")
        self.assertIn("`/checklist`", text)
        self.assertIn("`/fix-plan`", text)
        self.assertIn("`/ralph fix-plan`", text)

    def test_handoff_preserves_ralph_topic_and_marks_native_owner_resolution(self):
        text = (ROOT / "skills/todowrite/fix-plan-sync.md").read_text(encoding="utf-8")
        self.assertIn("/ralph fix-plan", text)
        self.assertIn("registered checklist", text)


if __name__ == "__main__":
    unittest.main()
