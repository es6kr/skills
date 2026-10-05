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


def extract_current_turn_text(transcript_path: str) -> str:
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

    start = 0
    for i in range(len(records) - 1, -1, -1):
        # A sidechain (subagent) record must not count as a main-turn
        # boundary or be attributed to the main turn's text -- its prose
        # could mention a trigger phrase, and its Skill(...) calls must
        # not satisfy a main-turn requirement (final-review Important I6).
        if records[i].get("isSidechain"):
            continue
        if _is_real_user(records[i]):
            start = i + 1
            break

    out = []
    for record in records[start:]:
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
                out.append(block.get("text", ""))
            elif block.get("type") == "tool_use" and block.get("name") == "Skill":
                skill_name = block.get("input", {}).get("skill", "")
                out.append(f'TOOL_CALL Skill("{skill_name}")')

    return "\n".join(out)
