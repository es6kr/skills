"""Standalone reviewed cron runner. No provider call without a bound durable request."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

class OutsideWindow(ValueError):
    """A non-sensitive, machine-checkable refusal before any CLI submission."""


MARKER = "AGY_FIRST_USE_READY"
PROMPT = ("This is a single first-use confirmation. Do not use tools, read or change files, "
          "execute commands, alter settings, plan work, or continue a previous conversation. "
          "Reply with exactly AGY_FIRST_USE_READY and nothing else.")
ENV_ALLOW = {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "HOME", "USERPROFILE",
             "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR", "PROGRAMFILES",
             "PROGRAMFILES(X86)", "PROGRAMDATA", "HOMEDRIVE", "HOMEPATH"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def file_digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def execute_request(directory, *, clock=None, run_cli=None):
    """Return a safe receipt; run_cli is an explicitly replaceable test collaborator."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    run_cli = run_cli or subprocess.run
    directory = Path(directory).resolve()
    payload = read_json(directory / "request.json")
    home = Path(payload["profile_home"]).resolve()
    state = home / "quota-reservation"
    key = payload["event_key"]
    if payload.get("version") != 1 or directory != state / "requests" / key:
        raise ValueError("Request location/version mismatch")
    if str(Path.home().resolve()) != payload["user_home"]:
        raise ValueError("OS user-home identity changed")
    policy = read_json(state / "policy.json")
    policy_digest = hashlib.sha256(canonical(policy).encode("utf-8")).hexdigest()
    if policy.get("enabled") is not True or policy.get("allow_existing_default") is not True:
        raise ValueError("Operator permission absent")
    if policy_digest != payload["policy_digest"]:
        raise ValueError("Operator policy changed")
    now = clock()
    due, expiry = (datetime.fromisoformat(payload[field]) for field in ("due", "expires"))
    if due.tzinfo is None or expiry.tzinfo is None or not due <= now <= expiry:
        raise OutsideWindow("Request not due or execution window expired")
    executable = Path(payload["executable"])
    if not executable.is_absolute() or file_digest(executable) != payload["executable_digest"]:
        raise ValueError("Existing CLI identity changed")
    if str(Path(policy["agy_executable"]).resolve()) != str(executable):
        raise ValueError("CLI target changed")
    if str(Path(__file__).resolve()) != payload["runner"]:
        raise ValueError("Runner identity changed")
    # An uncertain/previous submission consumes this request. No automatic replay.
    database = state / "ledger.sqlite3"
    if not database.is_file():
        raise ValueError("Reservation ledger absent")
    db = sqlite3.connect(database.as_uri() + "?mode=rw", uri=True, timeout=5, isolation_level=None)
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT payload,state FROM reservations WHERE event_key=?", (key,)).fetchone()
        if not row or row[1] != "scheduled" or canonical(payload) != row[0]:
            raise ValueError("Verified reservation binding absent")
        if db.execute("SELECT 1 FROM runs WHERE event_key=?", (key,)).fetchone():
            raise ValueError("Request already submitted; inspect the existing receipt")
        db.execute("INSERT INTO runs VALUES (?, 'submitted', NULL)", (key,))
        db.execute("COMMIT")
        command = [str(executable), "--print", PROMPT, "--disable-slash-commands",
                   "--output-format", "json", "--print-timeout", "120s"]
        # No API-key/provider overrides or account switching. Preserve existing OS login paths.
        env = {name: value for name, value in os.environ.items() if name.upper() in ENV_ALLOW}
        try:
            result = run_cli(command, cwd=str(directory), env=env, stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, encoding="utf-8", errors="strict",
                             timeout=135, shell=False)
            response = json.loads(result.stdout, object_pairs_hook=unique_object)
            if (result.returncode != 0 or not isinstance(response, dict)
                    or response.get("status") != "SUCCESS"
                    or type(response.get("num_turns")) is not int or response["num_turns"] != 1
                    or response.get("response") != MARKER):
                raise ValueError("First-use response not verified")
            receipt = {"state": "response_verified", "request": key, "response": MARKER,
                       "observed_at": clock().isoformat(), "quota_group_verified": False}
            db.execute("UPDATE runs SET state='response_verified',receipt=? WHERE event_key=?",
                       (canonical(receipt), key))
            return receipt
        except Exception:
            db.execute("UPDATE runs SET state='unknown' WHERE event_key=?", (key,))
            raise ValueError("First-use submission unknown; no automatic retry") from None
    finally:
        db.close()


def main():
    try:
        print(json.dumps(execute_request(Path.cwd()), sort_keys=True))
        return 0
    except OutsideWindow:
        print(json.dumps({"state": "not_verified", "automatic_retry": False,
                          "reason": "not_due_or_expired"}))
        return 2
    except Exception:
        # Never echo provider stdout/stderr, auth challenges, raw messages or private paths.
        print(json.dumps({"state": "not_verified", "automatic_retry": False,
                          "reason": "invalid_or_uncertain_request"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
