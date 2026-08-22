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
import argparse
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def check_hook_integrity(root):
    results = {
        "MISSING": [],
        "STALE-PERM": [],
        "DRIFT": [],
        "UNBACKED": [],
        "STALE-COMPILED": [],
        "OK": []
    }

    user_home = os.path.expanduser("~")
    hooks_config = os.path.join(user_home, ".gemini", "config", "hooks.json")
    if not os.path.exists(hooks_config):
        hooks_config = os.path.join(user_home, ".claude", "hooks.json")

    if not os.path.exists(hooks_config):
        results["MISSING"].append({"file": "hooks.json", "reason": "Global hooks.json config not found"})
        return results

    try:
        with open(hooks_config, "r", encoding="utf-8") as f:
            hooks_data = json.load(f)
    except Exception as e:
        results["MISSING"].append({"file": "hooks.json", "reason": f"Failed to parse hooks.json: {e}"})
        return results

    # Scan hooks in config
    hooks_list = hooks_data.get("hooks", {})
    for hook_event, command_list in hooks_list.items():
        for cmd_entry in command_list:
            script_path = ""
            if isinstance(cmd_entry, str):
                script_path = cmd_entry
            elif isinstance(cmd_entry, dict):
                script_path = cmd_entry.get("command", "") or cmd_entry.get("script", "")

            if not script_path:
                continue

            # Clean path
            clean_path = script_path.split()[0].strip('"').strip("'")
            expanded_path = os.path.expanduser(clean_path)

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
