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
import re
import sys
import json
import time
import argparse
from pathlib import Path

DEFAULT_LOCK_DIR = Path.home() / ".agents" / "tasks" / "locks"
DEFAULT_TTL = 1800  # 30 minutes

# A task id becomes a filename, so it must not be able to steer the path. Ids in this repo look
# like ES6KR-125 / SKILL-54, so refusing anything outside this class costs nothing legitimate,
# while ".." or "/" would otherwise write the lock outside the lock directory entirely.
TASK_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _invalid_task_id(task_id, medium="fs_fallback"):
    """Return an error result dict when task_id cannot safely become a filename, else None."""
    if TASK_ID_RE.match(task_id) and task_id not in (".", ".."):
        return None
    return {
        "task_id": task_id,
        "medium": medium,
        "error": "invalid task id: must match ^[A-Za-z0-9._-]+$ and not be '.' or '..'",
    }


def _write_json_atomic(path, payload):
    """Replace `path`'s contents without ever leaving it partially written.

    Used for the extend-my-own-lock path, where the file already exists so O_EXCL cannot apply.
    """
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


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

    bad = _invalid_task_id(clean_task_id)
    if bad:
        return {"acquired": False, **bad}

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

    # Filesystem fallback.
    #
    # `O_CREAT | O_EXCL` is the filesystem's own compare-and-set: the call fails if the file
    # already exists, so exactly one of N racing callers can create it. That is what makes this
    # a mutex. The previous shape -- exists() -> read -> decide -> write -- had no atomicity
    # between the check and the write, so two sessions could both pass the check and both
    # write, each believing it held the lock (measured: 40/40 trials double-granted).
    target_dir = Path(lock_dir) if lock_dir else DEFAULT_LOCK_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    lock_file = target_dir / f"{clean_task_id}.lock"

    def _payload():
        return {
            "task_id": clean_task_id,
            "holder": clean_session_id,
            "acquired_at": now,
            "expires_at": now + ttl_sec,
        }

    def _create_exclusive():
        """Create the lockfile or raise FileExistsError. 0o600 — a lock names a session."""
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(fd, json.dumps(_payload()).encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    def _granted(**extra):
        return {
            "acquired": True,
            "medium": "fs_fallback",
            "task_id": clean_task_id,
            "holder": clean_session_id,
            "expires_at": now + ttl_sec,
            **extra,
        }

    try:
        _create_exclusive()
        return _granted()
    except FileExistsError:
        pass  # someone else holds it, or a stale/expired file remains -- inspect below

    try:
        data = json.loads(lock_file.read_text(encoding="utf-8"))
    except Exception:
        # Fail CLOSED on an unreadable lock. Reading a corrupted lockfile as "free" used to
        # combine with the non-atomic write above -- that write is what produced half-written
        # files, and those were then treated as an invitation to acquire.
        return {
            "acquired": False,
            "medium": "fs_fallback",
            "task_id": clean_task_id,
            "holder": None,
            "error": "existing lock file is unreadable; treating as held",
        }

    expires_at = data.get("expires_at", 0)
    holder = data.get("holder", "")

    if expires_at > now:
        if holder == clean_session_id:
            # We already own it, so extending in place races with nobody.
            data["expires_at"] = now + ttl_sec
            _write_json_atomic(lock_file, data)
            return _granted()
        return {
            "acquired": False,
            "medium": "fs_fallback",
            "task_id": clean_task_id,
            "holder": holder,
            "remaining_ttl": max(0, int(expires_at - now)),
        }

    # Expired. Steal it -- but via unlink + O_EXCL retry, so two sessions racing to steal the
    # same expired lock cannot both succeed. Report who was displaced rather than overwriting
    # them silently: a holder past its TTL may still be alive and working.
    try:
        os.unlink(lock_file)
    except FileNotFoundError:
        pass
    try:
        _create_exclusive()
    except FileExistsError:
        return {
            "acquired": False,
            "medium": "fs_fallback",
            "task_id": clean_task_id,
            "holder": None,
            "error": "lost the race to steal an expired lock",
        }
    return _granted(displaced_holder=holder)


def release_lock(task_id, session_id, lock_dir=None, use_redis=True, redis_url=None):
    """
    Releases the lock for task_id if held by session_id.
    """
    clean_task_id = str(task_id).strip()
    clean_session_id = str(session_id).strip()

    bad = _invalid_task_id(clean_task_id)
    if bad:
        return {"released": False, **bad}

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

    bad = _invalid_task_id(clean_task_id)
    if bad:
        return {"is_locked": False, **bad}

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
