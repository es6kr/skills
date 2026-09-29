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


class TestTaskLockConcurrency(unittest.TestCase):
    """The fallback's mutual-exclusion guarantee, and the id validation that keeps it inside
    its own directory.

    The pre-existing tests above only exercise A-then-B ordering, which a check-then-write
    implementation survives. These two cases are the ones that actually distinguish a mutex
    from a file that happens to get written.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lock_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_concurrent_acquire_grants_exactly_one_holder(self):
        import multiprocessing as mp

        trials = 12
        for _ in range(trials):
            with tempfile.TemporaryDirectory() as d:
                with mp.Manager() as m:
                    barrier = m.Barrier(2)
                    with mp.Pool(2) as pool:
                        results = pool.map(
                            _concurrent_worker,
                            [(d, "sess-A", barrier), (d, "sess-B", barrier)],
                        )
            granted = [r for r in results if r[1]]
            self.assertEqual(
                len(granted),
                1,
                f"exactly one session may hold the lock, got {len(granted)}: {results}",
            )

    def test_traversal_shaped_task_id_is_rejected(self):
        nest = self.lock_dir / "locks"
        nest.mkdir()
        escaped = self.lock_dir / "ESCAPED.lock"

        res = task_lock.acquire_lock("../ESCAPED", "sess-x", lock_dir=str(nest), use_redis=False)

        self.assertFalse(res.get("acquired"), "a traversal-shaped task id must not acquire")
        self.assertFalse(escaped.exists(), f"no file may be written outside the lock dir: {escaped}")

    def test_ordinary_task_ids_still_acquire(self):
        for ok_id in ("ES6KR-125", "SKILL-54", "task_1", "a.b-c_9"):
            res = task_lock.acquire_lock(ok_id, "sess-ok", lock_dir=self.lock_dir, use_redis=False)
            self.assertTrue(res.get("acquired"), f"{ok_id} is a legitimate id and must acquire")


def _concurrent_worker(args):
    """Module-level so it is picklable by multiprocessing."""
    lock_dir, session, barrier = args
    barrier.wait()
    res = task_lock.acquire_lock("T-1", session, lock_dir=lock_dir, use_redis=False)
    return (session, bool(res.get("acquired")))
