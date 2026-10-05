"""Build (and cache) the enforce-marker registry across enabled skills."""
from __future__ import annotations

import glob
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "parse_enforce_markers", os.path.join(_HERE, "parse_enforce_markers.py")
)
assert _spec is not None and _spec.loader is not None
_parse_enforce_markers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_parse_enforce_markers)
parse_markers = _parse_enforce_markers.parse_markers


def _plugin_root(marketplaces_root: str, marketplace: str, plugin: str) -> str:
    """Resolve a plugin's root directory from its marketplace.json `source`.

    A marketplace's .claude-plugin/marketplace.json declares each plugin's
    `source` relative to the marketplace root. Two layouts exist in the
    wild: `source: "./"` (single-plugin marketplace -- the plugin root IS
    the marketplace root, e.g. es6kr-skills) and `source: "./plugins/<name>"`
    (multi-plugin marketplace -- each plugin has its own subdirectory).
    Reading marketplace.json is the only way to tell which one applies;
    assuming the plugins/<name> layout unconditionally silently discovers
    zero files for every source="./" marketplace (the bug this function
    fixes -- see tests/test_build_enforce_registry_discovery_layouts.py).
    """
    mp_json_path = os.path.join(marketplaces_root, marketplace, ".claude-plugin", "marketplace.json")
    try:
        with open(mp_json_path, "r", encoding="utf-8") as f:
            mp_data = json.load(f)
        for entry in mp_data.get("plugins", []):
            if entry.get("name") == plugin:
                source = entry.get("source", "./")
                return os.path.normpath(os.path.join(marketplaces_root, marketplace, source))
    except (OSError, json.JSONDecodeError):
        pass
    # Fallback: conventional plugins/<plugin> layout, for marketplaces whose
    # marketplace.json is missing/unreadable or lacks this plugin entry.
    return os.path.join(marketplaces_root, marketplace, "plugins", plugin)


def discover_skill_md_paths(enabled_plugins: dict, marketplaces_root: str) -> list:
    paths = []
    for key, enabled in enabled_plugins.items():
        if not enabled:
            continue
        plugin, _, marketplace = key.partition("@")
        if not marketplace:
            continue
        root = _plugin_root(marketplaces_root, marketplace, plugin)
        pattern = os.path.join(root, "skills", "**", "*.md")
        paths.extend(glob.glob(pattern, recursive=True))
    return paths


def build_registry(skill_md_paths: list, cache_path: str) -> list:
    cache = {"files": {}, "markers": {}}
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            try:
                cache = json.load(f)
            except json.JSONDecodeError:
                cache = {"files": {}, "markers": {}}

    registry = []
    for path in skill_md_paths:
        if not os.path.exists(path):
            cache["files"].pop(path, None)
            cache["markers"].pop(path, None)
            continue
        mtime = os.path.getmtime(path)
        if cache["files"].get(path) != mtime:
            cache["files"][path] = mtime
            cache["markers"][path] = parse_markers(path)
        registry.extend(cache["markers"].get(path, []))

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f)

    return registry
