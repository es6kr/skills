"""Extract the current turn's assistant text + Skill tool-calls from a
Claude Code session JSONL, for enforce-marker matching."""
from __future__ import annotations

import json


def _is_real_user(record: dict) -> bool:
    if record.get("type") != "user":
        return False
    content = record.get("message", {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return not any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content
        )
    return False


def extract_turn_info(transcript_path: str, previous: bool = False) -> tuple[str, set]:
    """Extract assistant turn text and invoked skill names from session JSONL.

    If previous=False: extracts current turn (assistant messages after the latest real user message).
    If previous=True: extracts the previous completed assistant turn (assistant messages
    belonging to the turn before the latest user message/turn).
    """
    records = []
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not previous:
        start = 0
        for i in range(len(records) - 1, -1, -1):
            if records[i].get("isSidechain"):
                continue
            if _is_real_user(records[i]):
                start = i + 1
                break
        target_records = records[start:]
    else:
        last_assistant_idx = -1
        for i in range(len(records) - 1, -1, -1):
            if records[i].get("isSidechain"):
                continue
            if records[i].get("type") == "assistant":
                last_assistant_idx = i
                break

        if last_assistant_idx == -1:
            return "", set()

        start = 0
        for i in range(last_assistant_idx - 1, -1, -1):
            if records[i].get("isSidechain"):
                continue
            if _is_real_user(records[i]):
                start = i + 1
                break

        end = len(records)
        for i in range(last_assistant_idx + 1, len(records)):
            if records[i].get("isSidechain"):
                continue
            if _is_real_user(records[i]):
                end = i
                break

        target_records = records[start:end]

    out_text = []
    invoked_skills = set()
    for record in target_records:
        if record.get("isSidechain"):
            continue
        if record.get("type") != "assistant":
            continue
        content = record.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                out_text.append(block.get("text", ""))
            elif block.get("type") == "tool_use" and block.get("name") == "Skill":
                skill_name = block.get("input", {}).get("skill", "")
                if skill_name:
                    invoked_skills.add(skill_name)
                out_text.append(f'TOOL_CALL Skill("{skill_name}")')

    return "\n".join(out_text), invoked_skills


def extract_current_turn_text(transcript_path: str) -> str:
    text, _ = extract_turn_info(transcript_path, previous=False)
    return text


def extract_previous_turn_text(transcript_path: str) -> str:
    text, _ = extract_turn_info(transcript_path, previous=True)
    return text


def extract_all_invoked_skills(transcript_path: str) -> set:
    """Return every skill name invoked via Skill(...) anywhere in the
    main (non-sidechain) transcript this session.

    Used to gate marker evaluation on whether the marker's owning skill
    was ever actually invoked this session (final-review Important I7) --
    without this, a marker fires on every turn regardless of whether its
    skill is being run or merely discussed/documented/edited.
    """
    skills = set()
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("isSidechain"):
                continue
            if record.get("type") != "assistant":
                continue
            content = record.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Skill":
                    skill_name = block.get("input", {}).get("skill", "")
                    if skill_name:
                        skills.add(skill_name)
    return skills
