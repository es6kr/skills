"""Integration test: the real consolidate/collect.md enforce marker is
actually caught by the generic parser + matcher engine."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COLLECT_MD = REPO_ROOT / "skills" / "consolidate" / "collect.md"


def _load(name, rel_path):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parse_enforce_markers = _load("parse_enforce_markers", "skills/hook-kit/scripts/parse_enforce_markers.py")
match_enforce_triggers = _load("match_enforce_triggers", "skills/hook-kit/scripts/match_enforce_triggers.py")
parse_markers = parse_enforce_markers.parse_markers
find_violations = match_enforce_triggers.find_violations


def test_collect_md_has_the_marker():
    markers = parse_markers(str(COLLECT_MD))
    assert any(
        m["requires_skill_call"] == "superpowers:receiving-code-review"
        for m in markers
    )


def test_missing_call_is_flagged_as_violation():
    markers = parse_markers(str(COLLECT_MD))
    turn_text = "moving on to Step 4 (classify) now"
    violations = find_violations(turn_text, markers, "same-turn")
    assert len(violations) == 1


def test_present_call_is_not_flagged():
    markers = parse_markers(str(COLLECT_MD))
    turn_text = (
        "moving on to Step 4 (classify) now\n"
        'TOOL_CALL Skill("superpowers:receiving-code-review")'
    )
    violations = find_violations(turn_text, markers, "same-turn")
    assert violations == []
