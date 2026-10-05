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


def discover_skill_md_paths(enabled_plugins: dict, marketplaces_root: str) -> list:
    paths = []
    for key, enabled in enabled_plugins.items():
        if not enabled:
            continue
        plugin, _, marketplace = key.partition("@")
        if not marketplace:
            continue
        pattern = os.path.join(
            marketplaces_root, marketplace, "plugins", plugin, "skills", "**", "*.md"
        )
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
