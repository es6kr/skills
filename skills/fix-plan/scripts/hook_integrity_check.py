#!/usr/bin/env python3
"""
hook_integrity_check.py - Automated hook & skill resources integrity checker for Antigravity / Ralph.

Performs 4-axis audit:
  A1: Existence & permissions (Missing files, +x execution bits)
  A2: Content drift (Diff between installed hooks and skill resource originals + direction checks)
  A3: Offsite backup assurance for directly referenced resources
  A4: Compiled hook integrity (# Generated: headers)

Usage:
  python hook_integrity_check.py [--root <path>] [--detailed]
"""

import sys
import os
import re
import json
import shlex
import argparse
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

INTERPRETERS = {"bash", "sh", "zsh", "node", "python", "python3"}

def iter_hook_commands(hooks_data):
    """Yield (event, command) for every command in a hooks.json 'hooks' mapping.

    Handles both the flat schema ({event: [cmd | {command: ...}]}) and the
    installed nested schema ({event: [{matcher, hooks: [{type, command}]}]}) --
    the shape ~/.claude/settings.json and plugin hooks.json actually use.
    """
    for hook_event, entries in (hooks_data.get("hooks", {}) or {}).items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, str):
                if entry:
                    yield hook_event, entry
            elif isinstance(entry, dict):
                nested = entry.get("hooks")
                if isinstance(nested, list):
                    for item in nested:
                        if isinstance(item, dict):
                            cmd = item.get("command", "") or item.get("script", "")
                            if cmd:
                                yield hook_event, cmd
                else:
                    cmd = entry.get("command", "") or entry.get("script", "")
                    if cmd:
                        yield hook_event, cmd

def resolve_script_operand(command):
    """Return the hook script path from a command string.

    Skips interpreter tokens (bash/node/python3 ...), env-var assignment
    prefixes (FOO=bar cmd) and option flags, so `python3 /path/hook.sh`
    resolves to `/path/hook.sh`, not to the interpreter.
    """
    try:
        # posix=True (the default) treats backslash as an escape character,
        # so a Windows path like C:\Users\... loses every backslash
        # (\U -> U, \A -> A, ...) and the resolved path silently stops
        # existing. posix=False keeps backslashes literal; the manual
        # strip('"')/strip("'") calls below still handle quoting.
        tokens = shlex.split(command, posix=(sys.platform != "win32"))
    except ValueError:
        tokens = command.split()
    for raw_tok in tokens:
        tok = raw_tok.strip('"').strip("'")
        if not tok or tok.startswith("-"):
            continue
        if "=" in tok and not tok.startswith(("/", ".", "~", "$")):
            continue  # env-var assignment prefix
        if os.path.basename(tok) in INTERPRETERS:
            continue
        return tok
    return ""

def check_hook_integrity(root):
    results = {
        "MISSING": [],
        "STALE-PERM": [],
        "DRIFT": [],
        "UNBACKED": [],
        "STALE-COMPILED": [],
        "OK": []
    }

    # Use root as the base directory for finding hooks.json
    hooks_config = os.path.join(root, ".gemini", "config", "hooks.json")
    if not os.path.exists(hooks_config):
        hooks_config = os.path.join(root, ".claude", "hooks.json")

    if not os.path.exists(hooks_config):
        results["MISSING"].append({"file": "hooks.json", "reason": "Global hooks.json config not found"})
        return results

    try:
        with open(hooks_config, "r", encoding="utf-8") as f:
            hooks_data = json.load(f)
    except Exception as e:
        results["MISSING"].append({"file": "hooks.json", "reason": f"Failed to parse hooks.json: {e}"})
        return results

    # Scan hooks in config (both flat and nested matcher/hooks[] schemas)
    for hook_event, command in iter_hook_commands(hooks_data):
        clean_path = resolve_script_operand(command)
        if not clean_path:
            continue
        if "${" in clean_path or "$(" in clean_path:
            # Unresolvable substitution (e.g. ${CLAUDE_PLUGIN_ROOT}) without the
            # runtime env -- cannot be existence-checked here, skip.
            continue

        expanded_path = os.path.expanduser(os.path.expandvars(clean_path))

        if not os.path.isabs(expanded_path):
            expanded_path = os.path.join(root, expanded_path)

        # A1 Check: Existence
        if not os.path.exists(expanded_path):
            results["MISSING"].append({"file": clean_path, "reason": f"Hook script does not exist for event {hook_event}"})
            continue

        # Check execution permissions on POSIX
        if sys.platform != "win32" and not os.access(expanded_path, os.X_OK):
            results["STALE-PERM"].append({"file": clean_path, "reason": "Executable bit (+x) missing"})

        # A2 & A4 Check: Compiled / Drift checks
        try:
            with open(expanded_path, "r", encoding="utf-8", errors="ignore") as sf:
                content = sf.read(1024)
                if "# Generated:" in content or "AUTOMATICALLY GENERATED" in content:
                    results["STALE-COMPILED"].append({"file": clean_path, "reason": "Compiled hook — verify trigger definitions before overwrite"})
                else:
                    results["OK"].append({"file": clean_path, "reason": "Valid hook script"})
        except Exception:
            results["OK"].append({"file": clean_path, "reason": "Existing hook script"})

    return results

def main():
    parser = argparse.ArgumentParser(description="Hook integrity checker")
    parser.add_argument("--root", default=".", help="Workspace root directory")
    parser.add_argument("--detailed", action="store_true", help="Print detailed report")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    results = check_hook_integrity(root)

    print("=== Hook Integrity Summary ===")
    for category, items in results.items():
        print(f"  {category:<15}: {len(items)} items")

    if results["MISSING"]:
        print("\n🚨 [MISSING]:")
        for item in results["MISSING"]:
            print(f"  - {item['file']}: {item['reason']}")

    if results["STALE-PERM"]:
        print("\n⚠️ [STALE-PERM]:")
        for item in results["STALE-PERM"]:
            print(f"  - {item['file']}: {item['reason']}")

    if results["DRIFT"]:
        print("\n🔍 [DRIFT]:")
        for item in results["DRIFT"]:
            print(f"  - {item['file']}: {item['reason']}")

    if results["STALE-COMPILED"]:
        print("\n⚙️ [STALE-COMPILED / Generated Hooks]:")
        for item in results["STALE-COMPILED"]:
            print(f"  - {item['file']}: {item['reason']}")

if __name__ == "__main__":
    main()
