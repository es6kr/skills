#!/usr/bin/env python3
"""Enforce explicit FA/fix skill loading before other work.

Runs as Hermes shell hooks. It only records a session gate for user messages
starting with ``fa:`` or ``fix:``, then blocks other tool calls until the
matching qualified skill has loaded successfully.
"""
from __future__ import annotations

import json
import os
import re
import runpy
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

PREFIX_SKILLS = {
    "fa": os.environ.get("HERMES_FA_SKILL", "fa"),
    "fix": os.environ.get("HERMES_FIX_SKILL", "fix"),
}
PREFIX_RE = re.compile(r"^\s*(fa|fix)\s*:", re.IGNORECASE)
HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
STATE_DIR = HOME / "hooks" / "skill-prefix-gate" / "state"
MAX_AGE_SECONDS = 3600


def read_payload() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def state_path(session_id: str) -> Path:
    safe = __import__("hashlib").sha256(session_id.encode()).hexdigest()
    return STATE_DIR / f"{safe}.json"


def write_state(session_id: str, skill: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    target = state_path(session_id)
    data = {"skill": skill, "created_at": time.time()}
    fd, raw = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=STATE_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(raw, target)
    finally:
        if os.path.exists(raw):
            os.unlink(raw)


def read_state(session_id: str) -> dict[str, Any] | None:
    target = state_path(session_id)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("skill"), str):
        target.unlink(missing_ok=True)
        return None
    if time.time() - float(data.get("created_at", 0)) > MAX_AGE_SECONDS:
        target.unlink(missing_ok=True)
        return None
    return data


def clear_state(session_id: str) -> None:
    state_path(session_id).unlink(missing_ok=True)


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False))


def credential_guard(payload: dict[str, Any]) -> int:
    """Delegate policy to the sibling source helper, without persisting raw data."""
    try:
        helper = Path(__file__).with_name("hermes_credential_preflight.py")
        result = runpy.run_path(str(helper))["handle_payload"](payload)
    except Exception:
        if payload.get("hook_event_name") == "pre_tool_call" and payload.get("tool_name") in {"clarify", "AskUserQuestion"}:
            emit({"action": "block", "message": "Credential preflight source helper unavailable; preserve existing credentials and repair the approved source binding."})
            return 2
        return 0
    if result is not None:
        emit(result)
        return 2 if result.get("action") == "block" else 0
    return 0


def main(prefix_skills: dict[str, str] | None = None) -> int:
    PREFIX_SKILLS.update(prefix_skills or {})
    payload = read_payload()
    event = str(payload.get("hook_event_name") or "")
    session_id = str(payload.get("session_id") or "")
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}

    if event == "pre_llm_call":
        message = str(extra.get("user_message") or "")
        match = PREFIX_RE.match(message)
        if not match:
            return 0
        skill = PREFIX_SKILLS[match.group(1).lower()]
        write_state(session_id, skill)
        emit({"context": f"[SKILL EXECUTION GATE] This message starts with `{match.group(1).lower()}:`. Before analysis, text, or any other tool, call `skill_view(name='{skill}')`. The gate blocks other tools and completion until that exact skill loads successfully."})
        return 0

    pending = read_state(session_id)
    if pending is None:
        return credential_guard(payload)
    skill = pending["skill"]
    tool_name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}

    if event == "pre_tool_call":
        if tool_name == "skill_view" and tool_input.get("name") == skill:
            return 0
        emit({"action": "block", "message": f"Skill execution gate: load `{skill}` with skill_view before any other tool."})
        return 2

    if event == "post_tool_call" and tool_name == "skill_view" and tool_input.get("name") == skill:
        # Fail closed: an ambiguous, malformed, or failed tool result must never
        # satisfy the gate. Native skill_view responses carry success: true.
        result = extra.get("result")
        if isinstance(result, dict) and result.get("success") is True:
            clear_state(session_id)
        elif isinstance(result, str):
            try:
                parsed = json.loads(result)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and parsed.get("success") is True:
                clear_state(session_id)
        return 0

    if event == "pre_verify":
        emit({"action": "continue", "message": f"Skill execution gate remains active: call `skill_view(name='{skill}')` successfully before finishing this response."})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
