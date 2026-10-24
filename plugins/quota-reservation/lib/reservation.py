"""Offline-testable reservation policy; no host imports or provider calls."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

NOTICE = re.compile(r"agy Refreshes in (?:(\d{1,2})h ?)?(?:(\d{1,2})m)?", re.ASCII | re.IGNORECASE)
EPOCH = 1420070400000
ORIGIN_FIELDS = ("platform", "chat_id", "thread_id", "user_id", "scope_id")
ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def file_digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def private_json(path, value):
    # Requests are unique immutable files, not executable templates from user text.
    with path.open("x", encoding="utf-8") as stream:
        path.chmod(0o600)
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        import os
        os.fsync(stream.fileno())


def instant(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timezone required")
    return parsed.astimezone(timezone.utc)


def handled(reply):
    return {"action": "handled", "reply": reply}


class Consumer:
    def __init__(self, *, settings, scheduler, state_dir, profile_home,
                 runner_script, clock=None):
        self.settings = deepcopy(settings)
        self.scheduler = scheduler
        self.home = Path(profile_home).resolve()
        self.state = Path(state_dir).resolve()
        self.runner = Path(runner_script).resolve()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        if self.state != self.home / "quota-reservation":
            raise ValueError("State must belong to the resolved profile home")
        if not self.runner.is_relative_to((self.home / "scripts").resolve()):
            raise ValueError("Runner must stay inside this profile scripts directory")

    def _authorize(self, platform, source):
        cfg = self.settings
        if not isinstance(cfg, dict) or cfg.get("enabled") is not True:
            return False
        if cfg.get("allow_existing_default") is not True:
            return False
        if not isinstance(cfg.get("approval_ref"), str) or not cfg["approval_ref"].strip():
            return False
        profile = cfg.get("profile")
        if not isinstance(profile, str) or not profile:
            return False
        if platform != "discord" or source.get("platform") != platform:
            return False
        if source.get("profile") not in (None, profile):
            return False
        actor = source.get("user_id")
        users = cfg.get("allowed_user_ids")
        if not isinstance(actor, str) or not isinstance(users, list) or actor not in users:
            return False
        origins = cfg.get("allowed_origins")
        origin = {key: source.get(key) for key in ORIGIN_FIELDS if key != "user_id"}
        if not isinstance(origins, list) or origin not in origins:
            return False
        if any(not isinstance(value, str) or not value for value in origin.values()):
            return False
        return True

    def _receipt(self, job, payload):
        if not isinstance(job, dict):
            return False
        try:
            return (
                isinstance(job.get("id"), str) and bool(re.fullmatch(r"[a-f0-9]{12}", job["id"]))
                and job.get("name") == payload["name"]
                and job.get("enabled") is True and job.get("state") == "scheduled"
                and job.get("no_agent") is True and job.get("deliver") == "origin"
                and job.get("origin") == payload["origin"]
                and job.get("script") == payload["runner"]
                and job.get("workdir") == payload["workdir"]
                and job.get("interpreter") == payload["interpreter"]
                and job.get("model") is None and job.get("provider") is None
                and type(job["repeat"]["times"]) is int and job["repeat"]["times"] == 1
                and type(job["repeat"]["completed"]) is int and job["repeat"]["completed"] == 0
                and job["schedule"]["kind"] == "once"
                and instant(job["schedule"]["run_at"]) == instant(payload["due"])
                and instant(job["next_run_at"]) == instant(payload["due"])
                and instant(payload["due"]) > self.clock()
            )
        except (KeyError, TypeError, ValueError):
            return False

    def _open(self):
        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        db = sqlite3.connect(self.state / "ledger.sqlite3", timeout=5, isolation_level=None)
        db.execute("CREATE TABLE IF NOT EXISTS reservations "
                   "(event_key TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL, job_id TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS runs "
                   "(event_key TEXT PRIMARY KEY, state TEXT NOT NULL, receipt TEXT)")
        return db

    async def __call__(self, *, session_key, platform, source, message_id, text):
        if not isinstance(source, dict) or not isinstance(text, str) or len(text) > 128:
            return None
        if not self._authorize(platform, source):
            return None
        match = NOTICE.fullmatch(text)
        if not match or not any(match.groups()):
            return None
        try:
            return self._book(source, message_id, text, match)
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
            # Do not leak private paths, raw messages, or provider diagnostics.
            return handled("Reservation not verified; no automatic resubmission.")

    def _book(self, source, message_id, text, match):
        if not isinstance(message_id, str) or not re.fullmatch(r"[0-9]{17,20}", message_id):
            raise ValueError("Trusted original Discord message id required")
        observed_ms = (int(message_id) >> 22) + EPOCH
        observed = datetime.fromtimestamp(observed_ms / 1000, timezone.utc)
        now = self.clock()
        if now.tzinfo is None or observed > now + timedelta(seconds=5):
            raise ValueError("Invalid observation time")
        hours, minutes = (int(value or 0) for value in match.groups())
        if minutes >= 60 or not 0 < hours * 60 + minutes <= 4320:
            raise ValueError("Countdown outside supported range")
        due = (observed + timedelta(hours=hours, minutes=minutes)).replace(second=0, microsecond=0)
        due += timedelta(minutes=1)
        if due <= now:
            return handled("Refresh deadline passed; not rescheduled from the current time.")
        cfg = self.settings
        if read_json(self.state / "policy.json") != cfg:
            raise ValueError("Operator policy changed")
        exe = Path(cfg["agy_executable"])
        if not exe.is_absolute() or not exe.is_file():
            raise ValueError("Existing executable required")
        if file_digest(self.runner) != file_digest(ROOT / "scripts" / "first_use.py"):
            raise ValueError("Reviewed profile runner copy required")
        origin = {key: source[key] for key in ORIGIN_FIELDS}
        event_key = digest([str(self.home), cfg["profile"], origin, message_id])
        folder = self.state / "requests" / event_key
        payload = {
            "version": 1, "event_key": event_key, "text_digest": digest(text),
            "profile_home": str(self.home), "user_home": str(Path.home().resolve()),
            "policy_digest": digest(cfg), "origin": origin,
            "due": due.isoformat(), "expires": (due + timedelta(minutes=5)).isoformat(),
            "executable": str(exe.resolve()), "executable_digest": file_digest(exe),
            "runner": str(self.runner), "interpreter": str(Path(sys.executable).resolve()),
            "name": "quota-first-use:" + event_key[:24], "workdir": str(folder),
        }
        db = self._open()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload,state,job_id FROM reservations WHERE event_key=?", (event_key,)).fetchone()
            if row:
                original = json.loads(row[0])
                if canonical(original) != canonical(payload):
                    raise ValueError("Original request binding changed")
                db.execute("COMMIT")
                return self._reconcile(db, payload, row[2])
            # Commit intent BEFORE a possibly ambiguous scheduler submission. Never retry it blindly.
            db.execute("INSERT INTO reservations VALUES (?,?,?,NULL)",
                       (event_key, canonical(payload), "submitting"))
            db.execute("COMMIT")
            folder.mkdir(mode=0o700, parents=True)
            private_json(folder / "request.json", payload)
            try:
                created = self.scheduler.create_job(
                    prompt=None, schedule=payload["due"], name=payload["name"], repeat=1,
                    deliver="origin", origin=origin, script=payload["runner"], no_agent=True,
                    workdir=payload["workdir"], interpreter=payload["interpreter"],
                    model=None, provider=None, pinned=False, paused=False,
                    attach_to_session=False, enabled_toolsets=[],
                )
                identifier = created.get("id") if isinstance(created, dict) else None
                if identifier:
                    db.execute("UPDATE reservations SET job_id=? WHERE event_key=?", (identifier, event_key))
                return self._reconcile(db, payload, identifier)
            except Exception:
                # A late uncertain submission must not revoke another delivery's verified receipt.
                db.execute("UPDATE reservations SET state='unknown' WHERE event_key=? AND state!='scheduled'",
                           (event_key,))
                return handled("Reservation submission unknown; no automatic retry.")
        finally:
            db.close()

    def _reconcile(self, db, payload, identifier):
        try:
            if not identifier:
                matches = [job for job in self.scheduler.list_jobs(include_disabled=True)
                           if job.get("name") == payload["name"] and job.get("workdir") == payload["workdir"]]
                # An older empty snapshot is uncertainty, not evidence against a newer receipt.
                if not matches:
                    raise LookupError("No matching reservation readback yet")
                identifier = matches[0].get("id") if len(matches) == 1 else None
            job = self.scheduler.get_job(identifier) if identifier else None
            if not self._receipt(job, payload):
                # Explicit missing/mismatched/disabled records still revoke execution eligibility.
                db.execute("UPDATE reservations SET state='unknown' WHERE event_key=?", (payload["event_key"],))
                return handled("Reservation not verified; submission unknown; no automatic retry.")
            db.execute("UPDATE reservations SET state='scheduled',job_id=? WHERE event_key=?",
                       (identifier, payload["event_key"]))
            return handled("First-use reservation scheduled: " + identifier + " at " + payload["due"])
        except Exception:
            # Transient lookup failure cannot downgrade an already verified reservation.
            db.execute("UPDATE reservations SET state='unknown' WHERE event_key=? AND state!='scheduled'",
                       (payload["event_key"],))
            return handled("Reservation not verified; submission unknown; no automatic retry.")
