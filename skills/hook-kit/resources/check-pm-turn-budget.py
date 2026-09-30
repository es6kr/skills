#!/usr/bin/env python3
"""check-pm-turn-budget.py — PostToolUse guard for PM session tool-call budget.

Tracks tool calls in PM-mode sessions (e.g. /fix-plan --pm).
Warns when the cumulative tool-call count reaches 30, preventing the agent
from sliding into full-stack direct implementation within a PM governance session.
"""

from __future__ import annotations
import json
import os
import sys
import tempfile

STATE_DIR = os.path.expanduser("~/.claude/state")
STATE_FILE = os.path.join(STATE_DIR, "pm-session-counters.json")
PM_BUDGET_LIMIT = 30


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


def is_pm_session(session_id: str, tool_input: dict) -> bool:
    # 1. Direct env variable
    if os.environ.get("PM_MODE") in ("1", "true", "TRUE"):
        return True

    # 2. Check if the current command invoked fix-plan --pm
    cmd = (
        tool_input.get("CommandLine", "")
        or tool_input.get("command", "")
        or tool_input.get("cmd", "")
    )
    if "--pm" in cmd and ("fix_plan" in cmd or "fix-plan" in cmd):
        return True

    # 3. Check persistent session state flag
    state = get_state()
    return state.get(session_id, {}).get("is_pm", False)


def track_pm_budget(tool_name: str, tool_input: dict, session_id: str) -> str | None:
    state = get_state()
    session_data = state.get(session_id, {"count": 0, "is_pm": False})

    # Activate PM flag if command matches
    cmd = (
        tool_input.get("CommandLine", "")
        or tool_input.get("command", "")
        or tool_input.get("cmd", "")
    )
    if "--pm" in cmd and ("fix_plan" in cmd or "fix-plan" in cmd):
        session_data["is_pm"] = True

    if not session_data.get("is_pm", False) and os.environ.get("PM_MODE") not in (
        "1",
        "true",
    ):
        return None

    session_data["is_pm"] = True
    count = session_data.get("count", 0) + 1
    session_data["count"] = count
    state[session_id] = session_data
    save_state(state)

    if count == PM_BUDGET_LIMIT:
        return (
            f"\n⚠️ [PM Turn Budget Limit Warning]\n"
            f"This PM session has accumulated {count} tool calls.\n"
            f"Rule Enforcement (Fix-Plan PM Role Mandatory Task Allocation & Dispatch Gate):\n"
            f"- Avoid self-implementing large tasks within a PM session.\n"
            f"- STOP implementation loops immediately and perform task allocation / handoff Ask\n"
            f"  across available channels (In-Session, Orca worktree split, Deep Tasks, Clawo/Ralph daemon).\n"
        )
    elif count > PM_BUDGET_LIMIT and count % 10 == 0:
        return (
            f"\n🚨 [PM Turn Budget Exceeded]\n"
            f"PM session tool calls ({count}) significantly exceed budget limit ({PM_BUDGET_LIMIT}).\n"
            f"Direct implementation is consuming PM session context window. Hand off immediately!\n"
        )

    return None


def run_self_test():
    test_session = "test-pm-session-9999"
    state = get_state()
    if test_session in state:
        del state[test_session]
        save_state(state)

    # 1. Non-PM command does not activate
    msg = track_pm_budget("Bash", {"command": "git status"}, test_session)
    assert msg is None

    # 2. PM command activates is_pm
    msg = track_pm_budget(
        "Bash", {"command": "python fix-plan.py --pm"}, test_session
    )
    state = get_state()
    assert state[test_session]["is_pm"] is True

    # 3. Simulate up to 29 calls
    for _ in range(2, PM_BUDGET_LIMIT):
        msg = track_pm_budget("Bash", {"command": "echo check"}, test_session)
        assert msg is None

    # 4. 30th call triggers warning
    msg = track_pm_budget("Bash", {"command": "echo check"}, test_session)
    assert msg is not None
    assert "PM Turn Budget Limit Warning" in msg

    # 5. Clean up
    state = get_state()
    if test_session in state:
        del state[test_session]
        save_state(state)

    print("check-pm-turn-budget self-test: ALL PASSED")


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

    msg = track_pm_budget(tool_name, tool_input, session_id)
    if msg:
        # exit 2 is what surfaces stderr to the model. On exit 0 the harness
        # discards it, which made this warning a silent no-op -- see
        # check-excessive-ci-polling.py for the same contract.
        print(msg, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
