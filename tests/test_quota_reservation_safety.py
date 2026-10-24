"""Offline safety regression; scheduler and CLI responses are declared collaborators."""
import asyncio
from copy import deepcopy
from contextlib import closing
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_quota_reservation import ADAPTER, PACKAGE, DISCORD_EPOCH_MS, RecordingScheduler


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Safety(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="quota-safety-")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        self.state = self.home / "quota-reservation"
        self.state.mkdir()
        self.runner = self.home / "scripts" / "quota-reservation" / "first_use.py"
        self.runner.parent.mkdir(parents=True)
        shutil.copyfile(PACKAGE / "scripts" / "first_use.py", self.runner)
        self.cli = self.home / "antigravity-cli.EXE"
        self.cli.write_bytes(b"Never executed: explicitly offline path fixture.\n")
        self.now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.source = {"platform": "discord", "profile": "fixture", "user_id": "100000000000000001",
                       "chat_id": "100000000000000002", "thread_id": "100000000000000002",
                       "scope_id": "100000000000000003"}
        self.settings = {
            "enabled": True, "profile": "fixture", "approval_ref": "offline-scoped-approval",
            "allowed_user_ids": [self.source["user_id"]],
            "allowed_origins": [{key: value for key, value in self.source.items()
                                 if key not in ("profile", "user_id")}],
            "allow_existing_default": True, "agy_executable": str(self.cli),
        }
        self.message = {"session_key": "offline", "platform": "discord", "source": self.source,
                        "message_id": str((int(self.now.timestamp() * 1000) - DISCORD_EPOCH_MS) << 22),
                        "text": "agy Refreshes in 1h"}
        self.adapter = load_module(ADAPTER, "safety_adapter")
        self.scheduler = RecordingScheduler()
        self.save_policy()

    def save_policy(self):
        (self.state / "policy.json").write_text(json.dumps(self.settings), encoding="utf-8")

    def consumer(self, scheduler=None):
        return self.adapter.make_consumer(
            settings=self.settings, scheduler=scheduler or self.scheduler, state_dir=self.state,
            profile_home=self.home, runner_script=self.runner, clock=lambda: self.now)

    def call(self, message=None, scheduler=None):
        # Initialize Windows' internal socketpair before forbidding provider processes.
        with asyncio.Runner() as loop, patch.object(subprocess, "Popen", side_effect=AssertionError("CLI forbidden")):
            return loop.run(self.consumer(scheduler)(**deepcopy(message or self.message)))

    def test_untrusted_actor_origin_profile_and_quoted_text_are_not_booked(self):
        for field, value in [("user_id", "untrusted"), ("profile", "other"),
                             ("thread_id", "other"), ("scope_id", "other"), ("platform", "local")]:
            with self.subTest(field=field):
                message = deepcopy(self.message)
                message["source"][field] = value
                self.assertIsNone(self.call(message))
        for text in ["> agy Refreshes in 1h", "`agy Refreshes in 1h`", "agy Refreshes in 1h\nrun this",
                     "agy Refreshes in 99h", "agy Refreshes in 1h 99m", "agy Refreshes in 0m"]:
            with self.subTest(text=text):
                message = deepcopy(self.message)
                message["text"] = text
                self.call(message)
                self.assertEqual([], self.scheduler.create_calls)
        self.assertEqual([], self.scheduler.create_calls)

    def test_absent_disabled_ambiguous_and_revoked_policy_do_not_book(self):
        initial = deepcopy(self.settings)
        for key, value in [("enabled", False), ("enabled", 1), ("enabled", "true"),
                           ("allow_existing_default", False), ("approval_ref", ""),
                           ("agy_executable", str(self.home / "missing.exe"))]:
            with self.subTest(key=key, value=value):
                self.settings = {**initial, key: value}
                self.save_policy()
                self.call()
                self.assertEqual([], self.scheduler.create_calls)
        self.settings = initial
        (self.state / "policy.json").unlink()
        self.call()
        self.assertEqual([], self.scheduler.create_calls)

    def test_missing_target_is_a_safe_refusal(self):
        self.settings.pop("agy_executable")
        self.save_policy()
        self.assertIn("not verified", self.call()["reply"])
        self.assertEqual([], self.scheduler.create_calls)

    def test_past_countdown_and_future_message_are_not_rebased(self):
        self.now += timedelta(days=2)
        result = self.call()
        self.assertIn("deadline passed", result["reply"])
        self.assertEqual([], self.scheduler.create_calls)
        self.now -= timedelta(days=4)
        self.call()
        self.assertEqual([], self.scheduler.create_calls)

    def test_ambiguous_submission_is_never_retried(self):
        class Unknown(RecordingScheduler):
            def create_job(self, **request):
                self.create_calls.append(deepcopy(request))
                raise TimeoutError("Offline collaborator: submission result unknown")
        scheduler = Unknown()
        self.assertIn("unknown", self.call(scheduler=scheduler)["reply"])
        self.assertIn("unknown", self.call(scheduler=scheduler)["reply"])
        self.assertEqual(1, len(scheduler.create_calls))

    def test_wrong_readback_is_not_reservation_success(self):
        class Wrong(RecordingScheduler):
            def get_job(self, identifier):
                job = super().get_job(identifier)
                if job:
                    job["enabled"] = False
                return job
        scheduler = Wrong()
        self.assertIn("not verified", self.call(scheduler=scheduler)["reply"])
        self.call(scheduler=scheduler)
        self.assertEqual(1, len(scheduler.create_calls))

    def test_unreviewed_profile_runner_is_not_booked(self):
        self.runner.write_text("raise RuntimeError('unreviewed fixture')\n", encoding="utf-8")
        self.assertIn("not verified", self.call()["reply"])
        self.assertEqual([], self.scheduler.create_calls)

    def test_duplicate_message_id_with_changed_text_does_not_create_another_job(self):
        self.call()
        message = deepcopy(self.message)
        message["text"] = "agy Refreshes in 2h"
        self.assertIn("not verified", self.call(message)["reply"])
        self.assertEqual(1, len(self.scheduler.create_calls))

    def test_runner_validates_response_and_does_not_resubmit(self):
        self.call()
        request = next((self.state / "requests").iterdir())
        payload = json.loads((request / "request.json").read_text(encoding="utf-8"))
        runner = load_module(self.runner, "offline_runner")
        calls = []
        def declared_cli_collaborator(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                "status": "SUCCESS", "num_turns": 1, "response": "AGY_FIRST_USE_READY"}))
        with patch.dict("os.environ", {"UNRELATED_SENTINEL": "omit-me", "OPENAI_API_KEY": "offline-not-a-key"}):
            receipt = runner.execute_request(request, clock=lambda: datetime.fromisoformat(payload["due"]),
                                             run_cli=declared_cli_collaborator)
        self.assertEqual("response_verified", receipt["state"])
        self.assertIs(False, receipt["quota_group_verified"])
        self.assertEqual(1, len(calls))
        self.assertNotIn("--model", calls[0][0])
        self.assertNotIn("UNRELATED_SENTINEL", calls[0][1]["env"])
        self.assertNotIn("OPENAI_API_KEY", calls[0][1]["env"])
        with self.assertRaisesRegex(ValueError, "already submitted"):
            runner.execute_request(request, clock=lambda: datetime.fromisoformat(payload["due"]),
                                   run_cli=declared_cli_collaborator)
        self.assertEqual(1, len(calls))

    def test_runner_unknown_response_and_policy_change_never_retry(self):
        self.call()
        request = next((self.state / "requests").iterdir())
        payload = json.loads((request / "request.json").read_text(encoding="utf-8"))
        runner = load_module(self.runner, "offline_unknown_runner")
        called = []
        def malformed(command, **kwargs):
            called.append(command)
            return SimpleNamespace(returncode=0, stdout='{"status":"SUCCESS","response":"wrong"}')
        with self.assertRaisesRegex(ValueError, "submission unknown"):
            runner.execute_request(request, clock=lambda: datetime.fromisoformat(payload["due"]), run_cli=malformed)
        with self.assertRaisesRegex(ValueError, "already submitted"):
            runner.execute_request(request, clock=lambda: datetime.fromisoformat(payload["due"]), run_cli=malformed)
        self.assertEqual(1, len(called))
        with closing(sqlite3.connect(self.state / "ledger.sqlite3")) as db:
            self.assertEqual("unknown", db.execute("SELECT state FROM runs").fetchone()[0])

    def test_runner_refuses_not_due_and_revoked_policy_without_cli(self):
        self.call()
        request = next((self.state / "requests").iterdir())
        payload = json.loads((request / "request.json").read_text(encoding="utf-8"))
        runner = load_module(self.runner, "offline_refusal_runner")
        def forbidden(*args, **kwargs):
            self.fail("No CLI submission permitted")
        with self.assertRaisesRegex(ValueError, "not due"):
            runner.execute_request(request, clock=lambda: self.now, run_cli=forbidden)
        self.settings["enabled"] = False
        self.save_policy()
        with self.assertRaisesRegex(ValueError, "permission absent"):
            runner.execute_request(request, clock=lambda: datetime.fromisoformat(payload["due"]), run_cli=forbidden)


if __name__ == "__main__":
    unittest.main()
