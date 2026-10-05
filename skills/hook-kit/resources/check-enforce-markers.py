#!/usr/bin/env python3
"""Stop hook: enforce same-turn <!-- enforce: ... --> markers across all
enabled skills. Reads hook JSON from stdin, exits 2 with a message on any
violation, exits 0 otherwise. Fails open on any internal error.

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

        # Loop-prevention guard (same convention as every other Stop hook
        # in this family, e.g. check-slash-command-skill-invoked.sh): a
        # Stop hook that denies gets re-invoked with stop_hook_active=true
        # on the resumed turn. Without this check, a violation whose
        # trigger text is already committed to the transcript (the model's
        # own prior response) re-fires on every retry, blocking forever.
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

        turn_text = extract_current_turn_text.extract_current_turn_text(transcript_path)
        violations = match_enforce_triggers.find_violations(turn_text, registry, "same-turn")

        if violations:
            # Stop hook schema (skills/hook-kit/add.md Step 3): blocking is
            # {"decision":"block","reason":"..."} on STDOUT, not stderr +
            # exit 2 -- Stop does not support hookSpecificOutput and the
            # reason string is the only feedback channel the model sees.
            reason_lines = ["[hook:check-enforce-markers] MANDATORY step skipped:"]
            for v in violations:
                reason_lines.append(f"  - {v['source_skill']}: {v['reason']}")
            print(json.dumps({"decision": "block", "reason": "\n".join(reason_lines)}))
            return 0

        return 0
    except Exception as exc:  # fail open — never block an unrelated turn
        print(f"[hook:check-enforce-markers] internal error, failing open: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
