#!/usr/bin/env python3
"""check-pm-turn-budget.py — PostToolUse guard for PM session tool-call budget.

Tracks tool calls in PM-mode sessions (e.g. /fix-plan --pm).
Warns when the cumulative tool-call count reaches 30, preventing the agent
from sliding into full-stack direct implementation within a PM governance session.

The guard is registered on the Bash matcher only, so a Bash command string is
its sole activation signal. Activation therefore has to distinguish a command
that *invokes* the pipeline from one that merely *mentions* it: quoted text and
heredoc bodies are masked out, commands whose job is to read or print text are
excluded, and the pipeline token must precede the --pm flag the way it does in
an invocation. Without that, `grep -n -- '--pm' <path>/fix_plan.md` activated
the guard, and because the flag is sticky for the session the budget warning
then fired every tenth tool call until the session ended.
"""

from __future__ import annotations
import json
import os
import re
import shlex
import sys
import tempfile

STATE_DIR = os.path.expanduser("~/.claude/state")
STATE_FILE = os.path.join(STATE_DIR, "pm-session-counters.json")
PM_BUDGET_LIMIT = 30

# How often the exceeded-budget warning repeats, and how many times. Bounding
# the escalations keeps a wrong activation from occupying the whole session.
ESCALATION_STEP = 10
MAX_ESCALATIONS = 3

# Commands whose purpose is to read, search or print text. A reference to the
# pipeline inside one of these is a mention, not an invocation.
TEXT_INSPECTION_CMDS = frozenset(
    {
        "ack", "ag", "awk", "cat", "cut", "diff", "echo", "egrep", "fgrep",
        "grep", "head", "jq", "less", "more", "nl", "printf", "rg", "sed",
        "sort", "strings", "tac", "tail", "tee", "uniq", "wc", "yq",
    }
)

INTERPRETERS = frozenset({"python", "python3", "uvx", "bash", "sh", "zsh"})
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _strip_heredoc(cmd: str) -> str:
    """Mask heredoc body lines so text inside stdin is not parsed as command tokens,
    while preserving preceding and following command lines."""
    lines = cmd.splitlines()
    res = []
    in_heredoc = False
    heredoc_term = ""
    for line in lines:
        if in_heredoc:
            if line.strip() == heredoc_term:
                in_heredoc = False
            continue
        m = re.search(r"<<-?\s*['\"]?([A-Za-z0-9_]+)['\"]?", line)
        if m:
            in_heredoc = True
            heredoc_term = m.group(1)
            # Remove <<MARKER from the command line while preserving surrounding tokens
            cleaned_line = line[:m.start()] + " " + line[m.end():]
            res.append(cleaned_line)
        else:
            res.append(line)
    return "\n".join(res)


def _split_commands(cmd: str) -> list[str]:
    """Split composite command lines on ;, &&, ||, |, and \n outside quoted spans."""
    parts = []
    curr = []
    in_single = False
    in_double = False
    i = 0
    while i < len(cmd):
        c = cmd[i]
        if c == "'" and not in_double:
            in_single = not in_single
            curr.append(c)
        elif c == '"' and not in_single:
            in_double = not in_double
            curr.append(c)
        elif not in_single and not in_double:
            if c in (";", "\n"):
                parts.append("".join(curr))
                curr = []
            elif c == "&" and i + 1 < len(cmd) and cmd[i + 1] == "&":
                parts.append("".join(curr))
                curr = []
                i += 1
            elif c == "|" and i + 1 < len(cmd) and cmd[i + 1] == "|":
                parts.append("".join(curr))
                curr = []
                i += 1
            elif c == "|":
                parts.append("".join(curr))
                curr = []
            else:
                curr.append(c)
        else:
            curr.append(c)
        i += 1
    if curr:
        parts.append("".join(curr))
    return [p.strip() for p in parts if p.strip()]


def _is_simple_cmd_pm(cmd: str) -> bool:
    """Inspect a single simple command to check if it executes fix_plan --pm."""
    try:
        tokens = shlex.split(cmd, comments=True)
    except ValueError:
        tokens = cmd.split()

    if not tokens:
        return False

    idx = 0
    while idx < len(tokens) and _ENV_ASSIGN_RE.match(tokens[idx]):
        idx += 1

    if idx >= len(tokens):
        return False

    prog = os.path.basename(tokens[idx])
    if prog in TEXT_INSPECTION_CMDS:
        return False

    has_pm_flag = any(t == "--pm" or t.startswith("--pm=") for t in tokens[idx:])
    if not has_pm_flag:
        return False

    pm_idx = -1
    for i, t in enumerate(tokens[idx:], start=idx):
        if t == "--pm" or t.startswith("--pm="):
            pm_idx = i
            break

    # If invoked via interpreter (e.g. python3 scripts/fix_plan.py --pm)
    if prog in INTERPRETERS:
        script_idx = idx + 1
        while script_idx < len(tokens) and tokens[script_idx].startswith("-") and not (tokens[script_idx] == "--pm" or tokens[script_idx].startswith("--pm=")):
            script_idx += 1
        if script_idx < len(tokens):
            script_name = os.path.basename(tokens[script_idx])
            if re.match(r"^fix[-_]plan[\w.-]*$", script_name) and script_idx < pm_idx:
                return True
        return False

    # Direct invocation (e.g. fix-plan --pm, ./scripts/fix_plan.py --pm)
    if re.match(r"^fix[-_]plan[\w.-]*$", prog) and idx < pm_idx:
        return True

    return False


def pm_mode_env() -> bool | None:
    """PM_MODE as a tri-state: True forces the guard on, False forces it off,
    None leaves the decision to command inspection. The off state matters for a
    session that knows the budget does not apply to it."""
    raw = os.environ.get("PM_MODE")
    if raw is None:
        return None
    return raw.strip().lower() in ("1", "true", "yes", "on")


def is_pm_invocation(cmd: str) -> bool:
    """True when the command actually runs the fix-plan PM pipeline."""
    if not cmd:
        return False
    cleaned = _strip_heredoc(cmd)
    for subcmd in _split_commands(cleaned):
        if _is_simple_cmd_pm(subcmd):
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


def is_pm_session(session_id: str, tool_input: dict) -> bool:
    # 1. Explicit env variable, in either direction
    forced = pm_mode_env()
    if forced is not None:
        return forced

    # 2. Does the current command invoke fix-plan --pm?
    cmd = (
        tool_input.get("CommandLine", "")
        or tool_input.get("command", "")
        or tool_input.get("cmd", "")
    )
    if is_pm_invocation(cmd):
        return True

    # 3. Persistent session state flag
    state = get_state()
    return state.get(session_id, {}).get("is_pm", False)


SESSION_TYPE_CHECK = (
    "- First classify this session type. Performing the PM role (triaging the backlog and\n"
    "  allocating it across channels) is what this budget targets. Building or measuring the\n"
    "  PM role itself — writing its probes, scoring model or rules — is a different session\n"
    "  and this warning is a false positive there: say so and carry on.\n"
)


def track_pm_budget(tool_name: str, tool_input: dict, session_id: str) -> str | None:
    forced = pm_mode_env()
    if forced is False:
        # An explicit off switch wins over everything, including a session that
        # was already flagged. Return before touching state so the flag cannot
        # be set by the very call that disabled the guard.
        return None

    state = get_state()
    session_data = state.get(session_id, {"count": 0, "is_pm": False})

    cmd = (
        tool_input.get("CommandLine", "")
        or tool_input.get("command", "")
        or tool_input.get("cmd", "")
    )
    if is_pm_invocation(cmd):
        session_data["is_pm"] = True

    if not session_data.get("is_pm", False) and not forced:
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
            f"{SESSION_TYPE_CHECK}"
            f"- Avoid self-implementing large tasks within a PM session.\n"
            f"- STOP implementation loops immediately and perform task allocation / handoff Ask\n"
            f"  across available channels (In-Session, Orca worktree split, Deep Tasks, Clawo/Ralph daemon).\n"
        )

    over = count - PM_BUDGET_LIMIT
    if over > 0 and over % ESCALATION_STEP == 0:
        escalation = over // ESCALATION_STEP
        if escalation <= MAX_ESCALATIONS:
            tail = (
                ""
                if escalation < MAX_ESCALATIONS
                else "This is the last escalation; the guard stays quiet from here.\n"
            )
            return (
                f"\n🚨 [PM Turn Budget Exceeded]\n"
                f"PM session tool calls ({count}) significantly exceed budget limit ({PM_BUDGET_LIMIT}).\n"
                f"{SESSION_TYPE_CHECK}"
                f"If this is the PM role itself, direct implementation is consuming the PM session\n"
                f"context window — hand off now.\n"
                f"{tail}"
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
        # PostToolUse stderr reaches the model only on exit 2; on exit 0 it is
        # discarded, so the budget warning would be written where nobody reads it.
        # Advisory only — the tool call already ran and is not being undone.
        # Same channel as skills/fix-plan/resources/warn-fixplan-item-schema.sh.
        print(msg, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
