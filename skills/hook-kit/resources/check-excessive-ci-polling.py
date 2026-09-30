#!/usr/bin/env python3
"""check-excessive-ci-polling.py — PreToolUse guard against excessive CI/status polling.

Blocks repetitive CI check commands or task status polling in interactive sessions
when streak reaches 8 consecutive calls, preventing context window bloat and token waste.
"""

from __future__ import annotations
import json
import os
import re
import sys
import tempfile

CI_POLL_PATTERNS = [
    re.compile(r"\bgh\s+pr\s+checks\b", re.IGNORECASE),
    re.compile(r"\bgh\s+run\s+watch\b", re.IGNORECASE),
    re.compile(r"\bgh\s+run\s+list\b", re.IGNORECASE),
    re.compile(r"\bmanage_task\b.*status", re.IGNORECASE),
]

STATE_DIR = os.path.expanduser("~/.claude/state")
STATE_FILE = os.path.join(STATE_DIR, "ci-polling-state.json")
MAX_POLL_STREAK = 8


def is_ci_poll_command(tool_name: str, tool_input: dict) -> bool:
    if tool_name == "manage_task":
        action = tool_input.get("Action", "") or tool_input.get("action", "")
        if action in ("status", "wait"):
            return True

    cmd = (
        tool_input.get("CommandLine", "")
        or tool_input.get("command", "")
        or tool_input.get("cmd", "")
    )
    if not cmd:
        return False

    for pat in CI_POLL_PATTERNS:
        if pat.search(cmd):
            return True
    return False


def get_state() -> dict:
    if not os.path.isfile(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state: dict):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = tempfile.NamedTemporaryFile(
            "w", dir=STATE_DIR, delete=False, encoding="utf-8"
        )
        json.dump(state, tmp, indent=2)
        tmp.flush()
        tmp.close()
        os.replace(tmp.name, STATE_FILE)
    except Exception:
        pass


def check_polling(tool_name: str, tool_input: dict, session_id: str) -> str | None:
    is_poll = is_ci_poll_command(tool_name, tool_input)
    state = get_state()
    session_data = state.get(session_id, {"streak": 0, "total": 0})

    if is_poll:
        streak = session_data.get("streak", 0) + 1
        total = session_data.get("total", 0) + 1
        session_data["streak"] = streak
        session_data["total"] = total
        state[session_id] = session_data
        save_state(state)

        if streak >= MAX_POLL_STREAK:
            return (
                f"HARD STOP: CI status or task polling has been repeated {streak} consecutive times.\n"
                f"To prevent interactive session context window bloat and auto-compact risk:\n"
                f"1. Delegate long-running CI monitoring to a background loop (Ralph/Clawo daemon),\n"
                f"2. Or schedule a one-shot timer with the `schedule` tool instead of synchronous polling loops."
            )
    else:
        # Reset streak on non-polling tool execution
        if session_data.get("streak", 0) > 0:
            session_data["streak"] = 0
            state[session_id] = session_data
            save_state(state)

    return None


def run_self_test():
    test_session = "test-session-1234"
    state = get_state()
    if test_session in state:
        del state[test_session]
        save_state(state)

    # 1. Non-poll command
    err = check_polling("Bash", {"command": "git status"}, test_session)
    assert err is None, f"Expected None, got {err}"

    # 2. Repeated CI check
    for i in range(1, MAX_POLL_STREAK):
        err = check_polling("Bash", {"command": "gh pr checks"}, test_session)
        assert err is None, f"Expected None on streak {i}, got {err}"

    # 3. 8th call should block
    err = check_polling("Bash", {"command": "gh pr checks"}, test_session)
    assert err is not None, "Expected HARD STOP error on 8th poll"
    assert "HARD STOP: CI status or task polling" in err, f"Wrong message: {err}"

    # 4. Clean up test session
    state = get_state()
    if test_session in state:
        del state[test_session]
        save_state(state)

    print("check-excessive-ci-polling self-test: ALL PASSED")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_self_test()
        sys.exit(0)

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        data = json.loads(raw)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "") or data.get("name", "")
    tool_input = data.get("tool_input", {}) or data.get("parameters", {})
    session_id = (
        data.get("session_id", "")
        or os.environ.get("CLAUDE_SESSION_ID")
        or os.environ.get("ANTIGRAVITY_CONVERSATION_ID")
        or "default-session"
    )

    err = check_polling(tool_name, tool_input, session_id)
    if err:
        print(err, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
