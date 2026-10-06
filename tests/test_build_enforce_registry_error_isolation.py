"""Regression tests for final-review Important I9 (per-file error
isolation) and I10 (corrupt cache shape must not permanently fail-open)."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "skills" / "hook-kit" / "scripts" / "build_enforce_registry.py"

_spec = importlib.util.spec_from_file_location("build_enforce_registry", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
build_enforce_registry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_enforce_registry)
build_registry = build_enforce_registry.build_registry


def _write(path, content=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def test_one_unreadable_file_does_not_crash_the_whole_registry(tmp_path):
    good = str(tmp_path / "skills" / "foo" / "good.md")
    bad = str(tmp_path / "skills" / "bar" / "bad.md")
    _write(good, '<!-- enforce: requires-skill-call="x" trigger="t" scope="same-turn" -->\n')
    _write(bad, "placeholder")
    os.chmod(bad, 0o000)  # unreadable
    cache_path = str(tmp_path / "cache.json")

    try:
        registry = build_registry([good, bad], cache_path)
    finally:
        os.chmod(bad, 0o644)  # restore so tmp_path cleanup can remove it

    assert {m["requires_skill_call"] for m in registry} == {"x"}


def test_shapeless_cache_json_does_not_crash(tmp_path):
    a = str(tmp_path / "skills" / "foo" / "a.md")
    _write(a, '<!-- enforce: requires-skill-call="x" trigger="t" scope="same-turn" -->\n')
    cache_path = str(tmp_path / "cache.json")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({}, f)  # valid JSON, wrong shape (no "files"/"markers" keys)

    registry = build_registry([a], cache_path)
    assert {m["requires_skill_call"] for m in registry} == {"x"}


def test_cache_with_wrong_type_does_not_crash(tmp_path):
    a = str(tmp_path / "skills" / "foo" / "a.md")
    _write(a, '<!-- enforce: requires-skill-call="x" trigger="t" scope="same-turn" -->\n')
    cache_path = str(tmp_path / "cache.json")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump([1, 2, 3], f)  # valid JSON, not even a dict

    registry = build_registry([a], cache_path)
    assert {m["requires_skill_call"] for m in registry} == {"x"}


def test_undecodable_file_does_not_crash_the_whole_registry(tmp_path):
    good = str(tmp_path / "skills" / "foo" / "good.md")
    bad = str(tmp_path / "skills" / "bar" / "bad.md")
    _write(good, '<!-- enforce: requires-skill-call="x" trigger="t" scope="same-turn" -->\n')
    _write(bad, "")
    with open(bad, "wb") as f:
        f.write(b"\x80\x81\x82\xff")
    cache_path = str(tmp_path / "cache.json")

    registry = build_registry([good, bad], cache_path)
    assert {m["requires_skill_call"] for m in registry} == {"x"}
