#!/usr/bin/env python3
"""UserPromptSubmit hook: advisory backstop for next-turn <!-- enforce: ... -->
markers. Stop hooks cannot see the following turn, so this catches a
next-turn violation one turn late, as plain stdout context (never blocks).

See skills/hook-kit/enforce-markers.md for the marker syntax reference.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_SCRIPTS_DIR, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Overridable via env var for tests -- production default is the real
# installed locations.
CACHE_PATH = os.environ.get(
    "ENFORCE_MARKERS_CACHE_PATH", os.path.expanduser("~/.claude/.cache/enforce-markers-registry.json")
)
SETTINGS_PATH = os.environ.get(
    "ENFORCE_MARKERS_SETTINGS_PATH", os.path.expanduser("~/.claude/settings.json")
)
MARKETPLACES_ROOT = os.environ.get(
    "ENFORCE_MARKERS_MARKETPLACES_ROOT", os.path.expanduser("~/.claude/plugins/marketplaces")
)


def main() -> int:
    if os.environ.get("RALPH_LOOP") == "1":
        return 0

    try:
        build_enforce_registry = _load("build_enforce_registry")
        extract_current_turn_text = _load("extract_current_turn_text")
        match_enforce_triggers = _load("match_enforce_triggers")

        hook_input = json.load(sys.stdin)
        # UserPromptSubmit does not resume/retry the way Stop does, but the
        # guard is cheap and keeps this entrypoint consistent with its
        # Stop-hook sibling (same family convention).
        if hook_input.get("stop_hook_active"):
            return 0

        transcript_path = hook_input.get("transcript_path", "")
        if not transcript_path or not os.path.exists(transcript_path):
            return 0

        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            enabled_plugins = json.load(f).get("enabledPlugins", {})

        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        paths = build_enforce_registry.discover_skill_md_paths(enabled_plugins, MARKETPLACES_ROOT)
        registry = build_enforce_registry.build_registry(paths, CACHE_PATH)

        previous_turn_text = extract_current_turn_text.extract_current_turn_text(transcript_path)
        active_skills = extract_current_turn_text.extract_all_invoked_skills(transcript_path)
        violations = match_enforce_triggers.find_violations(
            previous_turn_text, registry, "next-turn", active_skills=active_skills
        )

        if violations:
            lines = [
                "next-invocation continuation-chain guard "
                "(check-enforce-markers-next-turn): the prior turn appears to "
                "have skipped a MANDATORY next-turn step:"
            ]
            for v in violations:
                lines.append(f"  - {v['source_skill']}: {v['reason']}")
            print("\n".join(lines))

        return 0
    except Exception as exc:  # fail open
        # stderr, not stdout: UserPromptSubmit's stdout is injected as
        # context on every turn, so a persistent internal error would
        # otherwise pollute every future prompt with this message.
        print(f"[hook:check-enforce-markers-next-turn] internal error, failing open: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
