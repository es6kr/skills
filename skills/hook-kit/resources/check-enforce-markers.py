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


CACHE_PATH = os.path.expanduser("~/.claude/.cache/enforce-markers-registry.json")
SETTINGS_PATH = os.path.expanduser("~/.claude/settings.json")
MARKETPLACES_ROOT = os.path.expanduser("~/.claude/plugins/marketplaces")


def main() -> int:
    try:
        build_enforce_registry = _load("build_enforce_registry")
        extract_current_turn_text = _load("extract_current_turn_text")
        match_enforce_triggers = _load("match_enforce_triggers")

        hook_input = json.load(sys.stdin)
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
            lines = ["[hook:check-enforce-markers] MANDATORY step skipped:"]
            for v in violations:
                lines.append(f"  - {v['source_skill']}: {v['reason']}")
            print("\n".join(lines), file=sys.stderr)
            return 2

        return 0
    except Exception as exc:  # fail open — never block an unrelated turn
        print(f"[hook:check-enforce-markers] internal error, failing open: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
