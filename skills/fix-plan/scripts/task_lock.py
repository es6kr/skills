#!/usr/bin/env python3
"""
task_lock.py - Distributed Task Lock & Concurrency Coordinator (T2-L)

Provides atomic task claiming to prevent multi-session / multi-agent concurrency collisions.
Primary: Redis atomic key (SET task:lock:<task_id> <session_id> NX EX <ttl>).
Fallback: Local filesystem mutex lockfile (~/.agents/tasks/locks/<task_id>.lock) with TTL expiry check.

Usage:
  python3 task_lock.py --acquire --task ES6KR-125 --session session-123 [--ttl 1800]
  python3 task_lock.py --release --task ES6KR-125 --session session-123
  python3 task_lock.py --status --task ES6KR-125
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

DEFAULT_LOCK_DIR = Path.home() / ".agents" / "tasks" / "locks"
DEFAULT_TTL = 1800  # 30 minutes


def _get_redis_client(redis_url=None):
    url = redis_url or os.environ.get("REDIS_URL")
    if not url:
        return None
    try:
        import redis
        client = redis.from_url(url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def acquire_lock(task_id, session_id, ttl_sec=DEFAULT_TTL, lock_dir=None, use_redis=True, redis_url=None):
    """
    Attempts to acquire a distributed lock for task_id.
    """
    clean_task_id = str(task_id).strip()
    clean_session_id = str(session_id).strip()
    now = time.time()

    if use_redis:
        r = _get_redis_client(redis_url)
        if r is not None:
            try:
                key = f"task:lock:{clean_task_id}"
                acquired = r.set(key, clean_session_id, nx=True, ex=ttl_sec)
                if acquired:
                    return {
                        "acquired": True,
                        "medium": "redis",
                        "task_id": clean_task_id,
                        "holder": clean_session_id,
                        "expires_at": now + ttl_sec
                    }
                else:
                    holder = r.get(key)
                    ttl = r.ttl(key)
                    return {
                        "acquired": False,
                        "medium": "redis",
                        "task_id": clean_task_id,
                        "holder": holder,
                        "remaining_ttl": ttl
                    }
            except Exception as e:
                # Fallback to local lockfile if redis throws runtime error
                pass

    # Filesystem fallback
    target_dir = Path(lock_dir) if lock_dir else DEFAULT_LOCK_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    lock_file = target_dir / f"{clean_task_id}.lock"

    if lock_file.exists():
        try:
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            expires_at = data.get("expires_at", 0)
            holder = data.get("holder", "")

            # If existing lock is still valid and not expired
            if expires_at > now:
                if holder == clean_session_id:
                    # Re-acquire / extend
                    data["expires_at"] = now + ttl_sec
                    lock_file.write_text(json.dumps(data), encoding="utf-8")
                    return {
                        "acquired": True,
                        "medium": "fs_fallback",
                        "task_id": clean_task_id,
                        "holder": clean_session_id,
                        "expires_at": now + ttl_sec
                    }
                else:
                    return {
                        "acquired": False,
                        "medium": "fs_fallback",
                        "task_id": clean_task_id,
                        "holder": holder,
                        "remaining_ttl": max(0, int(expires_at - now))
                    }
        except Exception:
            pass  # Corrupted lockfile, overwrite

    # Create new lockfile
    lock_data = {
        "task_id": clean_task_id,
        "holder": clean_session_id,
        "acquired_at": now,
        "expires_at": now + ttl_sec
    }
    lock_file.write_text(json.dumps(lock_data), encoding="utf-8")

    return {
        "acquired": True,
        "medium": "fs_fallback",
        "task_id": clean_task_id,
        "holder": clean_session_id,
        "expires_at": now + ttl_sec
    }


def release_lock(task_id, session_id, lock_dir=None, use_redis=True, redis_url=None):
    """
    Releases the lock for task_id if held by session_id.
    """
    clean_task_id = str(task_id).strip()
    clean_session_id = str(session_id).strip()

    if use_redis:
        r = _get_redis_client(redis_url)
        if r is not None:
            try:
                key = f"task:lock:{clean_task_id}"
                holder = r.get(key)
                if holder == clean_session_id or holder is None:
                    r.delete(key)
                    return {"released": True, "medium": "redis", "task_id": clean_task_id}
                else:
                    return {"released": False, "reason": f"Lock held by another session: {holder}", "medium": "redis"}
            except Exception:
                pass

    target_dir = Path(lock_dir) if lock_dir else DEFAULT_LOCK_DIR
    lock_file = target_dir / f"{clean_task_id}.lock"

    if not lock_file.exists():
        return {"released": True, "medium": "fs_fallback", "task_id": clean_task_id}

    try:
        data = json.loads(lock_file.read_text(encoding="utf-8"))
        holder = data.get("holder", "")
        if holder == clean_session_id or not holder:
            lock_file.unlink(missing_ok=True)
            return {"released": True, "medium": "fs_fallback", "task_id": clean_task_id}
        else:
            return {"released": False, "reason": f"Lock held by another session: {holder}", "medium": "fs_fallback"}
    except Exception as e:
        lock_file.unlink(missing_ok=True)
        return {"released": True, "medium": "fs_fallback", "task_id": clean_task_id}


def get_lock_status(task_id, lock_dir=None, use_redis=True, redis_url=None):
    """
    Queries current lock status for task_id.
    """
    clean_task_id = str(task_id).strip()
    now = time.time()

    if use_redis:
        r = _get_redis_client(redis_url)
        if r is not None:
            try:
                key = f"task:lock:{clean_task_id}"
                holder = r.get(key)
                if holder:
                    ttl = r.ttl(key)
                    return {
                        "is_locked": True,
                        "medium": "redis",
                        "task_id": clean_task_id,
                        "holder": holder,
                        "remaining_ttl": ttl
                    }
                else:
                    return {"is_locked": False, "medium": "redis", "task_id": clean_task_id}
            except Exception:
                pass

    target_dir = Path(lock_dir) if lock_dir else DEFAULT_LOCK_DIR
    lock_file = target_dir / f"{clean_task_id}.lock"

    if not lock_file.exists():
        return {"is_locked": False, "medium": "fs_fallback", "task_id": clean_task_id}

    try:
        data = json.loads(lock_file.read_text(encoding="utf-8"))
        expires_at = data.get("expires_at", 0)
        holder = data.get("holder", "")
        if expires_at > now:
            return {
                "is_locked": True,
                "medium": "fs_fallback",
                "task_id": clean_task_id,
                "holder": holder,
                "remaining_ttl": max(0, int(expires_at - now))
            }
        else:
            lock_file.unlink(missing_ok=True)
            return {"is_locked": False, "medium": "fs_fallback", "task_id": clean_task_id}
    except Exception:
        return {"is_locked": False, "medium": "fs_fallback", "task_id": clean_task_id}


def main():
    parser = argparse.ArgumentParser(description="Distributed Task Lock Coordinator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--acquire", action="store_true", help="Acquire task lock")
    group.add_argument("--release", action="store_true", help="Release task lock")
    group.add_argument("--status", action="store_true", help="Check lock status")

    parser.add_argument("--task", required=True, help="Task identifier (e.g. ES6KR-125)")
    parser.add_argument("--session", default=None, help="Session UUID or name")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL, help="Lock TTL in seconds (default 1800)")
    parser.add_argument("--no-redis", action="store_true", help="Force filesystem fallback mode")

    args = parser.parse_args()
    session = args.session or os.environ.get("CONVERSATION_ID") or "anonymous-session"

    if args.acquire:
        res = acquire_lock(args.task, session, ttl_sec=args.ttl, use_redis=not args.no_redis)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res.get("acquired") else 1)
    elif args.release:
        res = release_lock(args.task, session, use_redis=not args.no_redis)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res.get("released") else 1)
    elif args.status:
        res = get_lock_status(args.task, use_redis=not args.no_redis)
        print(json.dumps(res, indent=2))
        sys.exit(0 if not res.get("is_locked") else 0)


if __name__ == "__main__":
    main()
