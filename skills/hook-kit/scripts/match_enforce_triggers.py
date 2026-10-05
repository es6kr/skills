"""Check a turn's text against the enforce-marker registry."""
from __future__ import annotations


def find_violations(turn_text: str, registry: list, scope_filter: str) -> list:
    violations = []
    for entry in registry:
        if entry.get("scope") != scope_filter:
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
