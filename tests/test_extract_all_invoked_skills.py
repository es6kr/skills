"""Tests for extract_all_invoked_skills() -- supports final-review
Important I7 (a marker fires on every turn regardless of whether its
owning skill was ever invoked this session, causing false positives when
a skill is merely being discussed/documented/edited rather than run)."""
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
extract_all_invoked_skills = extract_current_turn_text_mod.extract_all_invoked_skills


def _jsonl(tmp_path, records):
    path = str(tmp_path / "session.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path


def test_finds_skill_invoked_anywhere_in_session(tmp_path):
    records = [
        {"type": "user", "message": {"role": "user", "content": "first"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": "consolidate"}}
                ],
            },
        },
        {"type": "user", "message": {"role": "user", "content": "second"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "some other text"}],
            },
        },
    ]
    path = _jsonl(tmp_path, records)
    assert extract_all_invoked_skills(path) == {"consolidate"}


def test_no_skills_invoked_returns_empty_set(tmp_path):
    records = [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "no tool calls here"}],
            },
        },
    ]
    path = _jsonl(tmp_path, records)
    assert extract_all_invoked_skills(path) == set()


def test_sidechain_skill_invocations_are_excluded(tmp_path):
    """A subagent invoking a skill does not make that skill 'active' for
    the main agent's own marker evaluation."""
    records = [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {
            "type": "assistant",
            "isSidechain": True,
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": "consolidate"}}
                ],
            },
        },
    ]
    path = _jsonl(tmp_path, records)
    assert extract_all_invoked_skills(path) == set()
