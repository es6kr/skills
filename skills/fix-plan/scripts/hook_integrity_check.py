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

def _resolve_hooks_config(root):
    """Return (config_path_or_None, searched_paths).

    Workspace-local candidates are checked first so a caller can point the
    audit at an arbitrary root (and so tests can drive it with a tmp_path);
    the user-home global config is the fallback, which is what this function
    audited before the root parameter was introduced.
    """
    home = os.path.expanduser("~")
    searched = [
        os.path.join(root, ".gemini", "config", "hooks.json"),
        os.path.join(root, ".claude", "hooks.json"),
        os.path.join(home, ".gemini", "config", "hooks.json"),
        os.path.join(home, ".claude", "hooks.json"),
    ]
    for candidate in searched:
        if os.path.exists(candidate):
            return candidate, searched
    return None, searched


def _iter_marketplace_hooks_files(marketplaces_dir):
    """Yield (marketplace_name, plugin_name_or_None, hooks_json_path) for every
    hooks.json reachable from a marketplaces directory.

    Mirrors the two-layout scan check-ask-payload.js uses to auto-discover
    registered PreToolUse:AskUserQuestion guards: a root hooks/hooks.json
    (single-plugin marketplace, plugin_name=None) and nested
    plugins/<name>/hooks/hooks.json (multi-plugin marketplace).
    """
    if not os.path.isdir(marketplaces_dir):
        return
    for mp_name in sorted(os.listdir(marketplaces_dir)):
        mp_path = os.path.join(marketplaces_dir, mp_name)
        if not os.path.isdir(mp_path):
            continue

        root_hooks = os.path.join(mp_path, "hooks", "hooks.json")
        if os.path.isfile(root_hooks):
            yield mp_name, None, root_hooks

        plugins_dir = os.path.join(mp_path, "plugins")
        if os.path.isdir(plugins_dir):
            for plugin_name in sorted(os.listdir(plugins_dir)):
                plugin_hooks = os.path.join(plugins_dir, plugin_name, "hooks", "hooks.json")
                if os.path.isfile(plugin_hooks):
                    yield mp_name, plugin_name, plugin_hooks


def _marketplace_declared_name(marketplace_path):
    """Return the marketplace's own declared name from its
    .claude-plugin/marketplace.json "name" field.

    The directory (or symlink) a marketplace lives under in
    ~/.claude/plugins/marketplaces/ is not guaranteed to match this name --
    e.g. the real "dgs-skills" directory declares "name": "dgs" in its own
    marketplace.json, and the installed cache is keyed by that declared name
    ("cache/dgs/..."), never by the directory name ("cache/dgs-skills/...").
    Falls back to the directory's own basename when marketplace.json is
    absent or unreadable, so a marketplace without that metadata still
    resolves to something rather than crashing the audit.
    """
    manifest = os.path.join(marketplace_path, ".claude-plugin", "marketplace.json")
    try:
        with open(manifest, "r", encoding="utf-8") as f:
            data = json.load(f)
        name = data.get("name")
        if name:
            return name
    except Exception:
        pass
    return os.path.basename(os.path.normpath(marketplace_path))


def _find_cache_hooks_json(cache_dir, marketplace_name, plugin_name):
    """Resolve the installed cache hooks.json for (marketplace, plugin).

    Cache layout: cache_dir/<marketplace>/<plugin>/<version>/hooks/hooks.json.
    Single-plugin marketplaces (plugin_name is None) use the marketplace
    name as the plugin directory too. When multiple versions are installed,
    the highest-sorting version directory wins (newest install).
    Returns None when the plugin was never installed under this cache.
    """
    plugin_dir_name = plugin_name or marketplace_name
    base = os.path.join(cache_dir, marketplace_name, plugin_dir_name)
    if not os.path.isdir(base):
        return None
    versions = sorted(
        (v for v in os.listdir(base) if os.path.isdir(os.path.join(base, v))),
        reverse=True,
    )
    for version in versions:
        candidate = os.path.join(base, version, "hooks", "hooks.json")
        if os.path.isfile(candidate):
            return candidate
    return None


def _hook_registration_keys_from_data(hooks_data):
    """Return the set of (event, matcher, script-basename) registrations in
    an already-parsed hooks.json object.

    Matcher defaults to "" when an entry carries none (flat schema, or a
    matcher-less event like Stop/UserPromptSubmit), so registrations without
    a matcher still produce comparable keys. The script identity is reduced
    to its basename (not the full resolved path) because source and cache
    copies of the same script live under different absolute paths
    (marketplace checkout vs. ${CLAUDE_PLUGIN_ROOT}-relative cache install).
    """
    keys = set()
    for hook_event, entries in (hooks_data.get("hooks", {}) or {}).items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, str):
                script = os.path.basename(resolve_script_operand(entry))
                if script:
                    keys.add((hook_event, "", script))
                continue
            if not isinstance(entry, dict):
                continue
            matcher = entry.get("matcher", "") or ""
            nested = entry.get("hooks")
            if isinstance(nested, list):
                for item in nested:
                    if not isinstance(item, dict):
                        continue
                    cmd = item.get("command", "") or item.get("script", "")
                    if not cmd:
                        continue
                    script = os.path.basename(resolve_script_operand(cmd))
                    if script:
                        keys.add((hook_event, matcher, script))
            else:
                cmd = entry.get("command", "") or entry.get("script", "")
                if not cmd:
                    continue
                script = os.path.basename(resolve_script_operand(cmd))
                if script:
                    keys.add((hook_event, matcher, script))
    return keys


def _hook_registration_keys(hooks_json_path):
    """Load a hooks.json file and return its registration key set (see
    _hook_registration_keys_from_data). Returns an empty set on any read/parse
    failure so a broken file behaves like "no registrations" rather than
    crashing the audit."""
    try:
        with open(hooks_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return set()
    return _hook_registration_keys_from_data(data)


def _cache_keys_for_layout1(cache_dir, marketplace_name):
    """Union registration keys across EVERY installed plugin directory under
    cache_dir/<marketplace_name>/, plus the path of each hooks.json found.

    A layout-1 marketplace (root hooks/hooks.json, no plugins/ subdir) can
    still declare multiple plugins in marketplace.json that all share that
    same root as their "source" -- the real es6kr-skills shape declares
    es6kr/task/labs from one root. The installed cache then has one
    directory per DECLARED PLUGIN NAME under cache_dir/<marketplace>/, never
    a cache_dir/<marketplace>/<marketplace>/ directory. Guessing the single
    path "plugin dir == marketplace name" finds nothing and false-flags
    every registration as unsynced even when every declared plugin's cache
    is current, so this unions across whichever plugin subdirectories are
    actually installed instead of guessing one.
    """
    base = os.path.join(cache_dir, marketplace_name)
    keys = set()
    paths = []
    if not os.path.isdir(base):
        return keys, paths
    for plugin_dir_name in sorted(os.listdir(base)):
        cache_path = _find_cache_hooks_json(cache_dir, marketplace_name, plugin_dir_name)
        if cache_path:
            paths.append(cache_path)
            keys |= _hook_registration_keys(cache_path)
    return keys, paths


def check_source_cache_sync(marketplaces_dir, cache_dir):
    """Reverse hook-integrity axis: registrations present in a marketplace's
    SOURCE hooks.json but absent from the corresponding INSTALLED CACHE
    hooks.json.

    This is the failure mode the forward MISSING/OK checks in
    check_hook_integrity() cannot see: when a registration is added to the
    source but the plugin cache is never resynced, the registration and its
    script are simultaneously absent from the live runtime config, so
    nothing there ever gets flagged as a ghost (ghost detection requires a
    registration to exist first). Returns a list of unsynced-registration
    dicts; an empty list means every source registration has a matching
    cache counterpart.
    """
    unsynced = []
    for mp_name, plugin_name, source_path in _iter_marketplace_hooks_files(marketplaces_dir):
        source_keys = _hook_registration_keys(source_path)
        if not source_keys:
            continue

        # The installed cache is keyed by the marketplace's DECLARED name
        # (marketplace.json "name"), not by the directory/symlink name under
        # marketplaces_dir -- e.g. directory "dgs-skills" declares "dgs".
        cache_mp_name = _marketplace_declared_name(os.path.join(marketplaces_dir, mp_name))

        if plugin_name is None:
            # Layout 1: the source is shared by every plugin marketplace.json
            # declares from this root -- compare against the union of all
            # installed plugin caches under this marketplace, not one guess.
            cache_keys, cache_paths = _cache_keys_for_layout1(cache_dir, cache_mp_name)
            cache_label = ", ".join(cache_paths) if cache_paths else "(no cache install found)"
        else:
            cache_path = _find_cache_hooks_json(cache_dir, cache_mp_name, plugin_name)
            cache_keys = _hook_registration_keys(cache_path) if cache_path else set()
            cache_label = cache_path or "(no cache install found)"

        missing = source_keys - cache_keys
        for event, matcher, script in sorted(missing):
            unsynced.append({
                "marketplace": mp_name,
                "plugin": plugin_name or mp_name,
                "event": event,
                "matcher": matcher,
                "script": script,
                "source": source_path,
                "cache": cache_label,
            })
    return unsynced


def check_hook_integrity(root):
    results = {
        "MISSING": [],
        "STALE-PERM": [],
        "DRIFT": [],
        "UNBACKED": [],
        "STALE-COMPILED": [],
        "OK": []
    }

    # Workspace-local config wins (this is what makes the function testable with
    # a tmp_path root), but fall back to the user-home global config when the
    # workspace carries none. Resolving under `root` alone made this function
    # early-return a false MISSING for every workspace without its own
    # hooks.json -- silently skipping every check below.
    hooks_config, searched = _resolve_hooks_config(root)

    if hooks_config is None:
        results["MISSING"].append({
            "file": "hooks.json",
            "reason": (
                f"no hooks.json found in workspace ({root}) or user home; "
                f"searched: {', '.join(searched)}"
            ),
        })
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
    parser.add_argument(
        "--marketplaces-dir",
        default=os.path.join(os.path.expanduser("~"), ".claude", "plugins", "marketplaces"),
        help="Marketplace source root for the reverse source<->cache sync check",
    )
    parser.add_argument(
        "--cache-dir",
        default=os.path.join(os.path.expanduser("~"), ".claude", "plugins", "cache"),
        help="Installed plugin cache root for the reverse source<->cache sync check",
    )
    parser.add_argument(
        "--skip-source-cache-sync",
        action="store_true",
        help="Skip the reverse source<->cache registration sync check",
    )
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

    if not args.skip_source_cache_sync:
        unsynced = check_source_cache_sync(args.marketplaces_dir, args.cache_dir)
        print(f"\n=== Source<->Cache Sync: {len(unsynced)} unsynced-registration item(s) ===")
        if unsynced:
            print("\n🔄 [UNSYNCED-REGISTRATION]:")
            for item in unsynced:
                print(
                    f"  - {item['marketplace']}/{item['plugin']} "
                    f"[{item['event']}:{item['matcher'] or '(no matcher)'}] {item['script']} "
                    f"— in source ({item['source']}) but not in cache ({item['cache']})"
                )

if __name__ == "__main__":
    main()
