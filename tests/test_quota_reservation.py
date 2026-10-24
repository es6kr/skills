"""First RED contract for an admitted AGY refresh notice.

This is an offline policy-to-scheduler test, not native gateway or AGY acceptance.
The scheduler is an explicitly declared in-memory collaborator. It records job
creation and readback; it never executes a job or returns a provider response.
The future consumer must use the real post_gateway_admission keyword contract.
"""

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "plugins" / "quota-reservation"
ADAPTER = PACKAGE / "adapters" / "hermes" / "__init__.py"
DISCORD_EPOCH_MS = 1420070400000


class RecordingScheduler:
    """Test collaborator with the inspected native cron job record shape."""

    def __init__(self):
        self.jobs = {
            "000000000001": {
                "id": "000000000001",
                "name": "unrelated paused job",
                "enabled": False,
                "state": "paused",
                "next_run_at": None,
                "prompt": "Do not change this unrelated fixture.",
            }
        }
        self.create_calls = []
        self.read_calls = []

    def list_jobs(self, include_disabled=True):
        return [deepcopy(job) for job in self.jobs.values()
                if include_disabled or job.get("enabled", True)]

    def create_job(self, **request):
        self.create_calls.append(deepcopy(request))
        job_id = "000000000002"
        run_at = request["schedule"]
        job = deepcopy(request)
        job.update(
            id=job_id,
            enabled=not request.get("paused", False),
            state="paused" if request.get("paused", False) else "scheduled",
            next_run_at=None if request.get("paused", False) else run_at,
            schedule={"kind": "once", "run_at": run_at},
            repeat={"times": request["repeat"], "completed": 0},
            last_run_at=None,
            last_status=None,
        )
        self.jobs[job_id] = job
        return deepcopy(job)

    def get_job(self, job_id):
        self.read_calls.append(job_id)
        return deepcopy(self.jobs.get(job_id))


class TestAutomaticQuotaReservation(unittest.TestCase):
    def _load_adapter(self):
        # Missing product behavior is an assertion failure, not an import/setup error.
        self.assertTrue(
            ADAPTER.is_file(),
            "Automatic first-use reservation consumer is not implemented: "
            "plugins/quota-reservation/adapters/hermes/__init__.py is missing",
        )
        spec = importlib.util.spec_from_file_location("quota_reservation_test_adapter", ADAPTER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.addCleanup(sys.modules.pop, spec.name, None)
        self.assertTrue(callable(getattr(module, "make_consumer", None)),
                        "The Hermes adapter must expose make_consumer for the admitted hook")
        return module

    def test_admitted_refresh_creates_and_reads_one_enabled_oneshot(self):
        """A bound notice books once without asking an LLM to remember to do it."""
        with tempfile.TemporaryDirectory(prefix="quota-reservation-red-") as directory:
            fixture = Path(directory)
            scheduler = RecordingScheduler()
            unrelated = deepcopy(scheduler.jobs["000000000001"])
            observed = datetime(2030, 1, 1, 1, 2, 3, 456000, tzinfo=timezone.utc)
            observed_ms = int(observed.timestamp() * 1000)
            message_id = str(((observed_ms - DISCORD_EPOCH_MS) << 22) + 1)
            expected_due = (
                (observed + timedelta(hours=7, minutes=5)).replace(second=0, microsecond=0)
                + timedelta(minutes=1)
            )
            cli = fixture / "antigravity-cli.EXE"
            cli.write_bytes(b"Offline path fixture: booking must never execute this file.\n")
            source = {
                "platform": "discord",
                "profile": "fixture-profile",
                "user_id": "100000000000000001",
                "chat_id": "100000000000000002",
                "thread_id": "100000000000000002",
                "scope_id": "100000000000000003",
            }
            settings = {
                "enabled": True,
                "profile": "fixture-profile",
                "approval_ref": "offline-operator-first-use-once-v1",
                "allowed_user_ids": [source["user_id"]],
                "allowed_origins": [{
                    "platform": source["platform"],
                    "chat_id": source["chat_id"],
                    "thread_id": source["thread_id"],
                    "scope_id": source["scope_id"],
                }],
                "allow_existing_default": True,
                "agy_executable": str(cli),
            }
            incoming = {
                "session_key": "offline-quota-fixture-session",
                "platform": "discord",
                "source": source,
                "message_id": message_id,
                "text": "agy Refreshes in 7h 5m",
            }

            # The booking callback must neither invoke AGY nor contact a provider.
            with patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")), \
                    patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")), \
                    patch.object(subprocess, "Popen", side_effect=AssertionError("provider execution forbidden")):
                adapter = self._load_adapter()
                consumer = adapter.make_consumer(
                    settings=settings,
                    scheduler=scheduler,
                    state_dir=fixture / "private-state",
                    clock=lambda: observed + timedelta(seconds=2),
                )
                result = asyncio.run(consumer(**deepcopy(incoming)))
                self.assertIsInstance(result, dict)
                self.assertEqual("handled", result.get("action"))
                self.assertEqual(1, len(scheduler.create_calls),
                                 "An admitted refresh must register an actual job request")
                request = scheduler.create_calls[0]
                self.assertEqual(expected_due, datetime.fromisoformat(request["schedule"]))
                self.assertEqual(1, request["repeat"])
                self.assertIs(True, request["no_agent"],
                              "The first-use runner must not spend another scheduler-model turn")
                self.assertIs(False, request.get("paused", False))
                self.assertEqual("origin", request["deliver"])
                for field in ("platform", "chat_id", "thread_id", "user_id", "scope_id"):
                    self.assertEqual(source[field], request["origin"][field])
                self.assertEqual((PACKAGE / "scripts" / "first_use.py").resolve(),
                                 Path(request["script"]).resolve())
                self.assertIn("000000000002", scheduler.read_calls,
                              "Creation success alone is not an active-reservation receipt")
                receipt = scheduler.get_job("000000000002")
                self.assertIs(True, receipt["enabled"])
                self.assertEqual("scheduled", receipt["state"])
                self.assertEqual(expected_due, datetime.fromisoformat(receipt["next_run_at"]))
                self.assertEqual(unrelated, scheduler.jobs["000000000001"])
                self.assertIn("000000000002", result.get("reply", ""))

                repeated = asyncio.run(consumer(**deepcopy(incoming)))
                self.assertEqual("handled", repeated.get("action"))
                self.assertEqual(1, len(scheduler.create_calls),
                                 "Replaying the same admitted message must not create another job")
                self.assertEqual(unrelated, scheduler.jobs["000000000001"])


if __name__ == "__main__":
    unittest.main()
