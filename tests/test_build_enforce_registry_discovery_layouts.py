"""Regression tests for discover_skill_md_paths() marketplace layout handling.

Final review Critical C1: the original implementation only handled the
`plugins/<plugin>/skills/` layout and returned ZERO matches for a
single-plugin marketplace whose plugin `source` is `"./"` (the plugin root
IS the marketplace root) -- which is exactly es6kr-skills' own layout
(.claude-plugin/marketplace.json: "source": "./"), so this engine found
none of its own repo's markers, including the one this same PR added to
collect.md.
"""
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
discover_skill_md_paths = build_enforce_registry.discover_skill_md_paths


def _write(path, content=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _write_marketplace_json(root, marketplace, plugins):
    path = os.path.join(root, marketplace, ".claude-plugin", "marketplace.json")
    _write(path, json.dumps({"name": marketplace, "plugins": plugins}))


def test_source_dot_slash_layout_is_discovered(tmp_path):
    root = str(tmp_path)
    _write_marketplace_json(
        root, "mkt-a", [{"name": "p1", "source": "./"}]
    )
    _write(os.path.join(root, "mkt-a", "skills", "s1", "topic.md"), "content")

    paths = discover_skill_md_paths({"p1@mkt-a": True}, root)
    assert any("s1" in p for p in paths)


def test_conventional_plugins_subdir_layout_is_discovered(tmp_path):
    root = str(tmp_path)
    _write_marketplace_json(
        root, "mkt-b", [{"name": "p2", "source": "./plugins/p2"}]
    )
    _write(os.path.join(root, "mkt-b", "plugins", "p2", "skills", "s2", "topic.md"), "content")

    paths = discover_skill_md_paths({"p2@mkt-b": True}, root)
    assert any("s2" in p for p in paths)


def test_dict_source_externally_fetched_plugin_is_skipped_not_crashed(tmp_path):
    """Regression: claude-plugins-official lists many plugins with a dict
    `source` (git-subdir/url fetch spec) instead of a path string -- those
    plugins' files live in the plugin cache, not under this marketplace
    checkout, and are out of scope for local discovery. Must be skipped,
    never crash the whole discovery call."""
    root = str(tmp_path)
    _write_marketplace_json(
        root,
        "mkt-git",
        [
            {
                "name": "p-git",
                "source": {"source": "git-subdir", "url": "https://example.com/x.git", "path": "p"},
            }
        ],
    )

    paths = discover_skill_md_paths({"p-git@mkt-git": True}, root)
    assert paths == []


def test_missing_marketplace_json_falls_back_to_plugins_subdir(tmp_path):
    root = str(tmp_path)
    # No .claude-plugin/marketplace.json at all.
    _write(os.path.join(root, "mkt-c", "plugins", "p3", "skills", "s3", "topic.md"), "content")

    paths = discover_skill_md_paths({"p3@mkt-c": True}, root)
    assert any("s3" in p for p in paths)


def test_real_es6kr_skills_marketplace_discovers_collect_md():
    """Non-synthetic regression guard: discovery must find this very repo's
    own collect.md marker, against the real marketplaces/ layout this
    worktree is checked out under."""
    marketplaces_root = str(REPO_ROOT.parent)
    marketplace_name = REPO_ROOT.name
    assert os.path.exists(
        os.path.join(marketplaces_root, marketplace_name, ".claude-plugin", "marketplace.json")
    ), "test assumption: REPO_ROOT is a marketplace checkout with .claude-plugin/marketplace.json"

    paths = discover_skill_md_paths({f"es6kr@{marketplace_name}": True}, marketplaces_root)
    assert any(p.endswith(os.path.join("consolidate", "collect.md")) for p in paths), (
        f"discover_skill_md_paths found {len(paths)} files but none was "
        f"skills/consolidate/collect.md -- the source=\"./\" layout is still unhandled"
    )
