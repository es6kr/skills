"""Check a turn's text against the enforce-marker registry."""
from __future__ import annotations


def find_violations(
    turn_text: str,
    registry: list,
    scope_filter: str,
    active_skills=None,
    turn_skills=None,
) -> list:
    active_skill_names = (
        {name.rsplit(":", 1)[-1] for name in active_skills}
        if active_skills is not None
        else None
    )
    if turn_skills is not None:
        invoked_skill_names = {name.rsplit(":", 1)[-1] for name in turn_skills} | set(turn_skills)
    else:
        invoked_skill_names = None

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
        if active_skill_names is not None and entry["source_skill"] not in active_skill_names:
            continue

        trigger_text = entry.get("trigger") or entry.get("on_completion")
        if not trigger_text or trigger_text not in turn_text:
            continue

        req = entry["requires_skill_call"]
        req_bare = req.rsplit(":", 1)[-1]

        if invoked_skill_names is not None:
            if req in invoked_skill_names or req_bare in invoked_skill_names:
                continue
        else:
            required_call_marker = f'TOOL_CALL Skill("{req}")'
            required_call_marker_bare = f'TOOL_CALL Skill("{req_bare}")'
            if required_call_marker in turn_text or required_call_marker_bare in turn_text:
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
