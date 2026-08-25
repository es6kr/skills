import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import task_lock

class TestTaskLock(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lock_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fallback_lock_acquire_and_release(self):
        # When Redis is not available or disabled, use local filesystem lock
        task_id = "ES6KR-125"
        session_a = "session-aaa"
        session_b = "session-bbb"

        # Session A acquires lock
        res_a = task_lock.acquire_lock(task_id, session_a, lock_dir=self.lock_dir, use_redis=False)
        self.assertTrue(res_a["acquired"])
        self.assertEqual(res_a["holder"], session_a)

        # Session B attempts to acquire same lock -> should fail
        res_b = task_lock.acquire_lock(task_id, session_b, lock_dir=self.lock_dir, use_redis=False)
        self.assertFalse(res_b["acquired"])
        self.assertEqual(res_b["holder"], session_a)

        # Session A releases lock
        rel_a = task_lock.release_lock(task_id, session_a, lock_dir=self.lock_dir, use_redis=False)
        self.assertTrue(rel_a["released"])

        # Now Session B can acquire lock
        res_b2 = task_lock.acquire_lock(task_id, session_b, lock_dir=self.lock_dir, use_redis=False)
        self.assertTrue(res_b2["acquired"])
        self.assertEqual(res_b2["holder"], session_b)

    def test_lock_status_query(self):
        task_id = "ES6KR-999"
        session_a = "session-xyz"

        # Initially unlocked
        status = task_lock.get_lock_status(task_id, lock_dir=self.lock_dir, use_redis=False)
        self.assertFalse(status["is_locked"])

        # Lock acquired
        task_lock.acquire_lock(task_id, session_a, lock_dir=self.lock_dir, use_redis=False)
        status = task_lock.get_lock_status(task_id, lock_dir=self.lock_dir, use_redis=False)
        self.assertTrue(status["is_locked"])
        self.assertEqual(status["holder"], session_a)

if __name__ == "__main__":
    unittest.main()
