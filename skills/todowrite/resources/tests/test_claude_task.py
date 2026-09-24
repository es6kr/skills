#!/usr/bin/env python3
"""
Unit tests for `claude-task` CLI tool (`~/.agents/skills/todowrite/resources/claude-task.py`).
"""

import argparse
import os
import sys
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

# Add resources directory to sys.path
RESOURCES_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(RESOURCES_DIR))

import importlib.util
spec = importlib.util.spec_from_file_location("claude_task", str(RESOURCES_DIR / "claude-task.py"))
claude_task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(claude_task)

class TestClaudeTaskCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_claude_task_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_highwatermark_increment(self):
        id1 = claude_task.get_next_task_id(self.test_dir)
        self.assertEqual(id1, "1")
        
        id2 = claude_task.get_next_task_id(self.test_dir)
        self.assertEqual(id2, "2")
        
        hw_val = (self.test_dir / ".highwatermark").read_text().strip()
        self.assertEqual(hw_val, "2")

    def test_resolve_explicit_dir(self):
        resolved = claude_task.resolve_task_dir(custom_dir=str(self.test_dir))
        self.assertEqual(resolved, self.test_dir.resolve())

    def test_add_and_load_task(self):
        task_id = claude_task.get_next_task_id(self.test_dir)
        data = {
            "id": task_id,
            "subject": "Unit Test Task",
            "description": "Test Description",
            "activeForm": "Testing in progress",
            "status": "pending",
            "blocks": [],
            "blockedBy": []
        }
        claude_task.save_task(self.test_dir, data)

        loaded = claude_task.load_task(self.test_dir, task_id)
        self.assertEqual(loaded["id"], "1")
        self.assertEqual(loaded["subject"], "Unit Test Task")
        self.assertEqual(loaded["status"], "pending")

    def test_update_task_status_and_blocks(self):
        task_id = claude_task.get_next_task_id(self.test_dir)
        data = {
            "id": task_id,
            "subject": "Task 1",
            "description": "Desc",
            "activeForm": "Form",
            "status": "pending",
            "blocks": [],
            "blockedBy": []
        }
        claude_task.save_task(self.test_dir, data)

        # Update status and blocks
        data["status"] = "in_progress"
        data["blocks"] = ["2"]
        claude_task.save_task(self.test_dir, data)

        updated = claude_task.load_task(self.test_dir, task_id)
        self.assertEqual(updated["status"], "in_progress")
        self.assertEqual(updated["blocks"], ["2"])

    def test_delete_task(self):
        task_id = claude_task.get_next_task_id(self.test_dir)
        data = {"id": task_id, "subject": "Task to delete", "description": "", "activeForm": "", "status": "pending", "blocks": [], "blockedBy": []}
        claude_task.save_task(self.test_dir, data)

        task_file = self.test_dir / f"{task_id}.json"
        self.assertTrue(task_file.exists())

        task_file.unlink()
        self.assertFalse(task_file.exists())

    def _make_prune_args(self, retention_days=3, dry_run=False, purge=False):
        return argparse.Namespace(
            dir=str(self.test_dir), session=None, env=None,
            retention_days=retention_days, dry_run=dry_run, purge=purge,
        )

    def _write_task(self, task_id, status, age_days=0):
        data = {"id": task_id, "subject": f"Task {task_id}", "description": "", "activeForm": "", "status": status, "blocks": [], "blockedBy": []}
        claude_task.save_task(self.test_dir, data)
        if age_days:
            task_file = self.test_dir / f"{task_id}.json"
            old_time = time.time() - (age_days * 86400)
            os.utime(task_file, (old_time, old_time))

    def test_prune_archives_deleted_immediately(self):
        self._write_task("1", "deleted")
        claude_task.cmd_prune(self._make_prune_args())

        self.assertFalse((self.test_dir / "1.json").exists())
        archived = list(self.test_dir.glob(f"{claude_task.ARCHIVE_SUBDIR}/*/1.json"))
        self.assertEqual(len(archived), 1)

    def test_prune_archives_old_completed(self):
        self._write_task("2", "completed", age_days=10)
        claude_task.cmd_prune(self._make_prune_args(retention_days=3))

        self.assertFalse((self.test_dir / "2.json").exists())
        archived = list(self.test_dir.glob(f"{claude_task.ARCHIVE_SUBDIR}/*/2.json"))
        self.assertEqual(len(archived), 1)

    def test_prune_keeps_recent_completed_and_pending(self):
        self._write_task("3", "completed", age_days=1)
        self._write_task("4", "pending", age_days=10)
        self._write_task("5", "in_progress", age_days=10)
        claude_task.cmd_prune(self._make_prune_args(retention_days=3))

        self.assertTrue((self.test_dir / "3.json").exists())
        self.assertTrue((self.test_dir / "4.json").exists())
        self.assertTrue((self.test_dir / "5.json").exists())
        self.assertFalse((self.test_dir / claude_task.ARCHIVE_SUBDIR).exists())

    def test_prune_dry_run_no_changes(self):
        self._write_task("6", "deleted")
        self._write_task("7", "completed", age_days=10)
        claude_task.cmd_prune(self._make_prune_args(dry_run=True))

        self.assertTrue((self.test_dir / "6.json").exists())
        self.assertTrue((self.test_dir / "7.json").exists())
        self.assertFalse((self.test_dir / claude_task.ARCHIVE_SUBDIR).exists())

if __name__ == "__main__":
    unittest.main()
