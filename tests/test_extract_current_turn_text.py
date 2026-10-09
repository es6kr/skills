"""Unit tests for extract_current_turn_text.extract_current_turn_text()."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "skills" / "hook-kit" / "scripts" / "extract_current_turn_text.py"

_spec = importlib.util.spec_from_file_location("extract_current_turn_text", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
extract_current_turn_text_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extract_current_turn_text_mod)
extract_current_turn_text = extract_current_turn_text_mod.extract_current_turn_text


def _jsonl(tmp_path, records):
    path = str(tmp_path / "session.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path


def test_extracts_assistant_text_after_last_real_user_message(tmp_path):
    records = [
        {"type": "user", "message": {"role": "user", "content": "do the thing"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "before-dispatch: working on it"}],
            },
        },
    ]
    path = _jsonl(tmp_path, records)
    text = extract_current_turn_text(path)
    assert "before-dispatch: working on it" in text


def test_includes_tool_call_marker_for_skill_invocations(tmp_path):
    records = [
        {"type": "user", "message": {"role": "user", "content": "do the thing"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "dispatching now"},
                    {
                        "type": "tool_use",
                        "name": "Skill",
                        "input": {"skill": "superpowers:receiving-code-review"},
                    },
                ],
            },
        },
    ]
    path = _jsonl(tmp_path, records)
    text = extract_current_turn_text(path)
    assert 'TOOL_CALL Skill("superpowers:receiving-code-review")' in text


def test_ignores_turns_before_last_real_user_message(tmp_path):
    records = [
        {"type": "user", "message": {"role": "user", "content": "first request"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "old turn content"}],
            },
        },
        {"type": "user", "message": {"role": "user", "content": "second request"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "new turn content"}],
            },
        },
    ]
    path = _jsonl(tmp_path, records)
    text = extract_current_turn_text(path)
    assert "new turn content" in text
    assert "old turn content" not in text


def test_sidechain_assistant_text_is_excluded(tmp_path):
    """Regression for final-review Important I6: subagent (sidechain)
    records must not pollute the main turn's text -- a subagent's prose
    mentioning a trigger phrase must not be attributed to the main agent's
    turn, and a subagent's own Skill(...) call must not satisfy a
    main-turn requirement (the exact gap block-review-post-without-
    receiving-code-review.sh's own design note warned about)."""
    records = [
        {"type": "user", "message": {"role": "user", "content": "do the thing"}},
        {
            "type": "assistant",
            "isSidechain": True,
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "subagent prose: moving on to Step 4 (classify) now"},
                    {
                        "type": "tool_use",
                        "name": "Skill",
                        "input": {"skill": "superpowers:receiving-code-review"},
                    },
                ],
            },
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "main turn content"}],
            },
        },
    ]
    path = _jsonl(tmp_path, records)
    text = extract_current_turn_text(path)
    assert "main turn content" in text
    assert "subagent prose" not in text
    assert 'TOOL_CALL Skill("superpowers:receiving-code-review")' not in text


def test_sidechain_user_message_does_not_reset_turn_boundary(tmp_path):
    """A sidechain's own synthetic user-role message (e.g. a tool_result
    fed back to the subagent) must not be mistaken for a new main-turn
    boundary."""
    records = [
        {"type": "user", "message": {"role": "user", "content": "first request"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "main turn before sidechain"}],
            },
        },
        {
            "type": "user",
            "isSidechain": True,
            "message": {"role": "user", "content": "subagent's own prompt"},
        },
        {
            "type": "assistant",
            "isSidechain": True,
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "subagent reply"}],
            },
        },
    ]
    path = _jsonl(tmp_path, records)
    text = extract_current_turn_text(path)
    assert "main turn before sidechain" in text
    assert "subagent reply" not in text


def test_user_message_with_tool_result_is_not_a_real_user_boundary(tmp_path):
    records = [
        {"type": "user", "message": {"role": "user", "content": "first request"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "turn content"}],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "content": "result"}],
            },
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "more turn content"}],
            },
        },
    ]
    path = _jsonl(tmp_path, records)
    text = extract_current_turn_text(path)
    assert "turn content" in text
    assert "more turn content" in text
