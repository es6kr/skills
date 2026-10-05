"""Unit tests for match_enforce_triggers.find_violations()."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "skills" / "hook-kit" / "scripts" / "match_enforce_triggers.py"

_spec = importlib.util.spec_from_file_location("match_enforce_triggers", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
match_enforce_triggers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(match_enforce_triggers)
find_violations = match_enforce_triggers.find_violations

TRIGGER_MARKER = {
    "source_skill": "consolidate",
    "requires_skill_call": "superpowers:receiving-code-review",
    "trigger": "before-dispatch",
    "scope": "same-turn",
}

COMPLETION_MARKER = {
    "source_skill": "rag",
    "requires_skill_call": "next",
    "on_completion": "qdrant-import success",
    "scope": "same-turn",
}


def test_violation_when_trigger_fires_and_call_missing():
    turn_text = "before-dispatch: dispatching review subagent now"
    violations = find_violations(turn_text, [TRIGGER_MARKER], "same-turn")
    assert len(violations) == 1
    assert violations[0]["requires_skill_call"] == "superpowers:receiving-code-review"


def test_no_violation_when_required_call_present():
    turn_text = (
        "before-dispatch: dispatching review subagent now\n"
        'TOOL_CALL Skill("superpowers:receiving-code-review")'
    )
    violations = find_violations(turn_text, [TRIGGER_MARKER], "same-turn")
    assert violations == []


def test_prose_mention_of_call_does_not_count():
    turn_text = "before-dispatch: I should call superpowers:receiving-code-review here"
    violations = find_violations(turn_text, [TRIGGER_MARKER], "same-turn")
    assert len(violations) == 1


def test_no_violation_when_trigger_never_fires():
    turn_text = "unrelated turn content"
    violations = find_violations(turn_text, [TRIGGER_MARKER], "same-turn")
    assert violations == []


def test_on_completion_trigger_variant():
    turn_text = "qdrant-import success: embedded 5 chunks"
    violations = find_violations(turn_text, [COMPLETION_MARKER], "same-turn")
    assert len(violations) == 1
    assert violations[0]["requires_skill_call"] == "next"


def test_scope_filter_excludes_other_scope_entries():
    next_turn_marker = dict(TRIGGER_MARKER, scope="next-turn")
    turn_text = "before-dispatch: dispatching review subagent now"
    violations = find_violations(turn_text, [next_turn_marker], "same-turn")
    assert violations == []
