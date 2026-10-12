"""Acceptance tests: all ledger operations run under temporary HOME."""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RESOURCE = Path(__file__).resolve().parents[1]

class TestAgentTask(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory()
        self.home = Path(self.fixture.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_", "AGENT_", "OPENCLAW_"))}
        self.env["HOME"] = str(self.home)
    def tearDown(self):
        self.fixture.cleanup()
    def run_cli(self, *args, legacy=False, env=None):
        return subprocess.run([sys.executable, str(RESOURCE / ("claude-task.py" if legacy else "agent-task.py")), *args], env=env or self.env, capture_output=True, text=True)
    def test_alias_and_flag_placement(self):
        for legacy in (False, True):
            for args in (("--env", "agent", "--session", "A", "list", "--json"), ("list", "--json", "--env", "agent", "--session", "A")):
                r = self.run_cli(*args, legacy=legacy)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(json.loads(r.stdout), [])
    def test_reads_do_not_create_directories(self):
        for args in (("list", "--json"), ("dir",), ("show", "1"), ("prune", "--dry-run")):
            r = self.run_cli("--dir", str(self.home / "missing"), *args, legacy=True)
            self.assertEqual(r.returncode, 1 if args[0] == "show" else 0, r.stderr)
            self.assertFalse((self.home / "missing").exists())
    def test_invalid_sessions_fail_without_writes(self):
        for sid in ("../escape", "/absolute", "a/b", "a\\b", ".", "..", ""):
            r = self.run_cli("--env", "agent", "--session", sid, "add", "-s", "bad", legacy=True)
            self.assertNotEqual(r.returncode, 0, sid)
        self.assertFalse((self.home / ".agents").exists())
    def test_openclaw_missing_identity_fails_closed(self):
        env = dict(self.env, OPENCLAW_SERVICE_KIND="gateway", CLAUDE_SESSION_ID="stale")
        for args in (("add", "-s", "bad"), ("update", "1", "--status", "completed"), ("delete", "1"), ("prune",)):
            r = self.run_cli("--env", "agent", *args, legacy=True, env=env)
            self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.home / ".agents").exists())
    def test_isolation_rotation_and_preserved_identity(self):
        for sid, subject in (("A", "first"), ("B", "rotated"), ("A", "same identity")):
            r = self.run_cli("--env", "agent", "--session", sid, "add", "-s", subject)
            self.assertEqual(r.returncode, 0, r.stderr)
        for sid, want in (("A", ["first", "same identity"]), ("B", ["rotated"])):
            r = self.run_cli("--env", "agent", "--session", sid, "list", "--json")
            self.assertEqual([t["subject"] for t in json.loads(r.stdout)], want)
    def test_precedence_and_default_preservation(self):
        target = self.home / ".agents/tasks/default"
        target.mkdir(parents=True)
        original = b'{"id":"999","subject":"preserve","status":"pending"}'
        (target / "999.json").write_bytes(original)
        before = (target / "999.json").stat().st_mtime_ns
        env = dict(self.env, CLAUDE_TASK_DIR=str(target), AGENT_TASK_DIR=str(self.home / "other"))
        r = self.run_cli("--env", "agent", "--session", "A", "add", "-s", "new", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((target / "1000.json").exists())
        r = self.run_cli("--dir", str(self.home / "explicit"), "add", "-s", "override", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.home / "explicit/1.json").exists())
        self.assertEqual((target / "999.json").read_bytes(), original)
        self.assertEqual((target / "999.json").stat().st_mtime_ns, before)
    def test_concurrent_add_and_update_do_not_lose_records(self):
        ledger = self.home / "parallel"
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda i: self.run_cli("--dir", str(ledger), "add", "-s", str(i), legacy=True), range(60)))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results if r.returncode])
        tasks = [json.loads(p.read_text()) for p in ledger.glob("*.json")]
        self.assertEqual(len(tasks), 60)
        self.assertEqual({t["subject"] for t in tasks}, {str(i) for i in range(60)})
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda i: self.run_cli("--dir", str(ledger), "update", "1", "--add-block", str(i), legacy=True), range(20)))
        self.assertTrue(all(r.returncode == 0 for r in results))
        self.assertEqual(set(json.loads((ledger / "1.json").read_text())["blocks"]), {str(i) for i in range(20)})
    def test_writer_keeps_resolved_ledger_while_waiting_for_lock(self):
        # Another session can become newest while the selected ledger lock is acquired.
        import argparse
        from contextlib import contextmanager
        import importlib.util
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location("agent_task_fixture", RESOURCE / "agent-task.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        base = self.home / "tasks"
        a, b = base / "A", base / "B"
        a.mkdir(parents=True)
        b.mkdir()
        os.utime(a, (200, 200))
        os.utime(b, (100, 100))
        original_lock = module.ledger_lock
        @contextmanager
        def contender(task_dir):
            with original_lock(task_dir):
                os.utime(b, (4000000000, 4000000000))
                yield
        args = argparse.Namespace(dir=None, session=None, env="agent", subject="owned A", description=None,
                                  active_form=None, status="pending", blocks=None, blocked_by=None)
        with patch.dict(os.environ, self.env, clear=True), patch.object(module, "AGENTS_TASKS_BASE", base), patch.object(module, "ledger_lock", contender):
            module.cmd_add(args)
        self.assertTrue((a / "1.json").exists())
        self.assertFalse((b / "1.json").exists())

    def test_task_id_traversal_rejected(self):
        outside = self.home / "victim.json"
        outside.write_text('{"id":"victim"}')
        ledger = self.home / "ledger"
        ledger.mkdir()
        for cmd in ("show", "delete", "update"):
            r = self.run_cli("--dir", str(ledger), cmd, "../victim", legacy=True)
            self.assertNotEqual(r.returncode, 0)
        self.assertTrue(outside.exists())

if __name__ == "__main__":
    unittest.main()
