"""Unit tests for build_enforce_registry.build_registry() / discover_skill_md_paths()."""
from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "skills" / "hook-kit" / "scripts" / "build_enforce_registry.py"

_spec = importlib.util.spec_from_file_location("build_enforce_registry", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
build_enforce_registry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_enforce_registry)
build_registry = build_enforce_registry.build_registry
discover_skill_md_paths = build_enforce_registry.discover_skill_md_paths


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def test_build_registry_parses_all_given_files(tmp_path):
    a = str(tmp_path / "skills" / "foo" / "a.md")
    b = str(tmp_path / "skills" / "bar" / "b.md")
    _write(a, '<!-- enforce: requires-skill-call="x" trigger="t" scope="same-turn" -->\n')
    _write(b, '<!-- enforce: requires-skill-call="y" trigger="t" scope="same-turn" -->\n')
    cache_path = str(tmp_path / "cache.json")

    registry = build_registry([a, b], cache_path)
    assert {m["requires_skill_call"] for m in registry} == {"x", "y"}


def test_cache_is_reused_when_mtime_unchanged(tmp_path):
    a = str(tmp_path / "skills" / "foo" / "a.md")
    _write(a, '<!-- enforce: requires-skill-call="x" trigger="t" scope="same-turn" -->\n')
    cache_path = str(tmp_path / "cache.json")

    build_registry([a], cache_path)
    with open(cache_path) as f:
        cached = json.load(f)
    first_mtime = cached["files"][a]

    build_registry([a], cache_path)
    with open(cache_path) as f:
        cached_again = json.load(f)
    assert cached_again["files"][a] == first_mtime


def test_cache_invalidates_on_mtime_change(tmp_path):
    a = str(tmp_path / "skills" / "foo" / "a.md")
    _write(a, '<!-- enforce: requires-skill-call="x" trigger="t" scope="same-turn" -->\n')
    cache_path = str(tmp_path / "cache.json")

    build_registry([a], cache_path)
    time.sleep(0.01)
    _write(a, '<!-- enforce: requires-skill-call="z" trigger="t" scope="same-turn" -->\n')
    os.utime(a, None)  # force mtime bump regardless of filesystem resolution

    registry = build_registry([a], cache_path)
    assert {m["requires_skill_call"] for m in registry} == {"z"}


def test_discover_skill_md_paths_only_enabled_plugins(tmp_path):
    root = str(tmp_path)
    _write(
        os.path.join(root, "mkt-a", "plugins", "p1", "skills", "s1", "topic.md"),
        "enabled plugin file",
    )
    _write(
        os.path.join(root, "mkt-b", "plugins", "p2", "skills", "s2", "topic.md"),
        "disabled plugin file",
    )
    enabled = {"p1@mkt-a": True, "p2@mkt-b": False}
    paths = discover_skill_md_paths(enabled, root)
    assert any("s1" in p for p in paths)
    assert not any("s2" in p for p in paths)
