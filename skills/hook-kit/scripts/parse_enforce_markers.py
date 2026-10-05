"""Parse <!-- enforce: ... --> markers out of a skill .md file.

See skills/hook-kit/enforce-markers.md for the marker syntax reference.
"""
from __future__ import annotations

import os
import re

_MARKER_RE = re.compile(r"<!--\s*enforce:\s*(.*?)-->", re.DOTALL)
_ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
_VALID_SCOPES = {"same-turn", "next-turn"}


def _skill_name_from_path(file_path: str) -> str:
    # .../skills/<skill-name>/<topic>.md -> <skill-name>
    parts = os.path.normpath(file_path).split(os.sep)
    if "skills" in parts:
        idx = parts.index("skills")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return os.path.basename(os.path.dirname(file_path))


def parse_markers(file_path: str) -> list:
    parse_markers.last_errors = []
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    source_skill = _skill_name_from_path(file_path)
    results = []
    for match in _MARKER_RE.finditer(text):
        attrs = dict(_ATTR_RE.findall(match.group(1)))

        requires = attrs.get("requires-skill-call")
        scope = attrs.get("scope")
        trigger = attrs.get("trigger")
        on_completion = attrs.get("on-completion")

        if not requires:
            parse_markers.last_errors.append(
                f"{file_path}: marker missing requires-skill-call, skipped"
            )
            continue
        if scope not in _VALID_SCOPES:
            parse_markers.last_errors.append(
                f"{file_path}: marker for {requires!r} missing scope "
                f"(or invalid scope {scope!r}), skipped"
            )
            continue

        entry = {
            "source_skill": source_skill,
            "requires_skill_call": requires,
            "scope": scope,
        }
        if on_completion:
            entry["on_completion"] = on_completion
        elif trigger:
            entry["trigger"] = trigger
        else:
            parse_markers.last_errors.append(
                f"{file_path}: marker for {requires!r} has neither trigger "
                f"nor on-completion, skipped"
            )
            continue

        results.append(entry)

    return results


parse_markers.last_errors = []
