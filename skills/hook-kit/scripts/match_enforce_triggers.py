"""Check a turn's text against the enforce-marker registry."""
from __future__ import annotations


def find_violations(turn_text: str, registry: list, scope_filter: str, active_skills=None) -> list:
    violations = []
    for entry in registry:
        if entry.get("scope") != scope_filter:
            continue

        # Active-skill gate (final-review Important I7): a marker fires
        # on EVERY turn regardless of whether its owning skill was ever
        # invoked this session -- the marker's own trigger phrase often
        # appears verbatim in that skill's documentation, so merely
        # discussing/editing/documenting the skill (as this very engine's
        # development does) is a false positive. `active_skills=None`
        # preserves the original ungated behavior (e.g. for callers that
        # don't have a whole-session view, like synthetic unit tests).
        if active_skills is not None and entry["source_skill"] not in active_skills:
            continue

        trigger_text = entry.get("trigger") or entry.get("on_completion")
        if not trigger_text or trigger_text not in turn_text:
            continue

        required_call_marker = f'TOOL_CALL Skill("{entry["requires_skill_call"]}")'
        if required_call_marker in turn_text:
            continue

        violations.append(
            {
                "source_skill": entry["source_skill"],
                "requires_skill_call": entry["requires_skill_call"],
                "reason": (
                    f"trigger {trigger_text!r} fired but "
                    f"Skill(\"{entry['requires_skill_call']}\") was not called"
                ),
            }
        )
    return violations
