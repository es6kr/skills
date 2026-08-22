#!/usr/bin/env python3
"""
Verify hook registrations in every hooks.json in this repository.

Two independent failure classes are checked:

1. Duplicate registration — the same (event, matcher, script-basename) registered
   more than once. The hook then fires twice on every trigger.

2. Ghost registration — a command references a script path that does not exist.
   The hook dies with exit 127, which the harness cannot distinguish from
   "hook ran and raised no objection": the guard silently enforces nothing while
   still appearing in the registration list. This is how relocating a script
   without updating its registration disables a guard with no visible signal.

Ported from es6kr/claude-plugins (PR #23, merged) — that repo hit this exact
gap: a hook-relocation commit moved a script into another skill's resources/
without updating hooks/hooks.json's registration path, silently disabling the
guard with no signal. es6kr/skills hit the identical class independently
(hooks.json#L43 audit, 2026-08-18) — 3 ghost paths found by manual grep before
this CI check existed. This script is that PR's verify-hooks-json.py, adapted
to this repo (structurally generic already — no es6kr/claude-plugins-specific
assumptions beyond the shared hooks/hooks.json + ${CLAUDE_PLUGIN_ROOT} layout
convention both repos use).
"""

import json
import re
import sys
from pathlib import Path

# `${CLAUDE_PLUGIN_ROOT}/a/b.sh`, `"${CLAUDE_PLUGIN_ROOT}/a/b.sh"`, `$CLAUDE_PLUGIN_ROOT/a/b.sh`
#
# The path ends differently depending on whether the reference is quoted, and getting
# that wrong produces a FALSE ghost report rather than a missed one: a truncated path
# does not exist, so a legitimate registration would fail CI. So when an opening quote
# precedes the reference, the path runs to the matching close quote (this is the only
# form that can legally contain spaces); otherwise it ends at whitespace, a quote, or
# a shell metacharacter that terminates the word (`;` `&` `|` `)`).
PLUGIN_ROOT_REF = re.compile(
    r'(?P<q>["\'])?\$\{?CLAUDE_PLUGIN_ROOT\}?(?P<path>/.*?)(?(q)(?P=q)|(?=["\'\s;&|)]|$))'
)


def extract_script_basename(cmd: str) -> str:
    # Match script basename like foo.sh, bar.py, baz.js
    m = re.search(r'([a-zA-Z0-9_-]+\.(?:sh|py|js|ts))\b', cmd)
    if m:
        return m.group(1)
    # No script token — an inline shell command. The whole command becomes the
    # duplicate key, which is what we want: registering the same inline command twice
    # under one (event, matcher) is as much a duplicate as registering a script twice.
    return cmd.strip()


def extract_plugin_root_paths(cmd: str) -> list:
    """Return every ${CLAUDE_PLUGIN_ROOT}-relative path referenced by a command."""
    return [m.group("path").lstrip("/") for m in PLUGIN_ROOT_REF.finditer(cmd)]


def plugin_root_for(filepath: Path) -> Path:
    """Resolve ${CLAUDE_PLUGIN_ROOT} for a given hooks.json.

    A plugin's hooks live at <plugin-root>/hooks/hooks.json, so the plugin root is
    always the grandparent — for the repo-root plugin (source "./") that is the
    repository root, for plugins/<name> it is that plugin's directory.
    """
    return filepath.parent.parent


def iter_commands(data: dict):
    """Yield (event, matcher, command) for every registered hook."""
    for event, entries in data.get("hooks", {}).items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            matcher = entry.get("matcher", "*")
            for hook in entry.get("hooks", []):
                yield event, matcher, hook.get("command", "")


def check_hooks_file(filepath: Path) -> tuple:
    """Return (errors, checked_paths, skipped_commands) for one hooks.json."""
    if not filepath.is_file():
        return [], 0, 0

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return [f"Failed to parse JSON in {filepath}: {e}"], 0, 0

    errors = []
    seen = set()
    root = plugin_root_for(filepath)
    checked_paths = 0
    skipped_commands = 0

    for event, matcher, cmd in iter_commands(data):
        # 1. duplicate registration
        script = extract_script_basename(cmd)
        key = (event, matcher, script)
        if key in seen:
            errors.append(
                f"Duplicate hook registration in {filepath}: event='{event}', "
                f"matcher='{matcher}', script='{script}' (command: {cmd})"
            )
        seen.add(key)

        # 2. ghost registration
        rel_paths = extract_plugin_root_paths(cmd)
        if not rel_paths:
            # Inline shell or an absolute/other-variable path — not resolvable here.
            skipped_commands += 1
            continue
        for rel in rel_paths:
            checked_paths += 1
            if not (root / rel).is_file():
                errors.append(
                    f"Ghost hook registration in {filepath}: event='{event}', "
                    f"matcher='{matcher}' points at a missing script "
                    f"'{rel}' (resolved: {root / rel})"
                )

    return errors, checked_paths, skipped_commands


def collect_hooks_files(root: Path) -> list:
    files = [root / "hooks" / "hooks.json"]
    # Nested plugin/skill hook files. es6kr/skills currently has one hooks.json
    # at the repo root (the repo-root plugin owns it), but keep the globs so a
    # nested hooks.json under plugins/<name> or skills/<name> is covered the
    # day one appears — mirrors the source repo's own forward-looking comment.
    files.extend(root.glob("plugins/**/hooks/hooks.json"))
    files.extend(root.glob("skills/**/hooks/hooks.json"))
    return [f for f in files if f.is_file()]


def main():
    root = Path(__file__).resolve().parent.parent

    all_errors = []
    total_checked = 0
    total_skipped = 0
    for fp in collect_hooks_files(root):
        errs, checked, skipped = check_hooks_file(fp)
        all_errors.extend(errs)
        total_checked += checked
        total_skipped += skipped

    # Report coverage unconditionally, so a check that verified nothing is visible
    # rather than reading as a pass.
    print(
        f"Resolved {total_checked} ${{CLAUDE_PLUGIN_ROOT}} script path(s); "
        f"{total_skipped} command(s) had no resolvable path and were skipped."
    )

    if all_errors:
        print("❌ Found hook registration problems:")
        for err in all_errors:
            print(f"  - {err}")
        sys.exit(1)

    print("✅ No duplicate or ghost hook registrations found in hooks.json files.")


if __name__ == "__main__":
    main()
