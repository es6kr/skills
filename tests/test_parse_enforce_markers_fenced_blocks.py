"""Regression test for final-review Important I4: markers inside fenced
code blocks (used to document the marker syntax itself) must not be
parsed as live markers -- otherwise enforce-markers.md's own syntax
examples register as real rules for every session."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "skills" / "hook-kit" / "scripts" / "parse_enforce_markers.py"
ENFORCE_MARKERS_DOC = REPO_ROOT / "skills" / "hook-kit" / "enforce-markers.md"

_spec = importlib.util.spec_from_file_location("parse_enforce_markers", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
parse_enforce_markers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parse_enforce_markers)
parse_markers = parse_enforce_markers.parse_markers


def _write(tmp_path, name, content):
    skill_dir = os.path.join(tmp_path, "skills", "fake-skill")
    os.makedirs(skill_dir, exist_ok=True)
    path = os.path.join(skill_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_marker_inside_fenced_block_is_not_parsed(tmp_path):
    path = _write(
        tmp_path,
        "docs.md",
        "Example syntax:\n\n"
        "```\n"
        '<!-- enforce: requires-skill-call="<skill-name>" trigger="<example>" scope="same-turn" -->\n'
        "```\n",
    )
    assert parse_markers(path) == []


def test_marker_outside_fence_in_same_file_is_still_parsed(tmp_path):
    path = _write(
        tmp_path,
        "docs.md",
        "Example syntax:\n\n"
        "```\n"
        '<!-- enforce: requires-skill-call="<skill-name>" trigger="<example>" scope="same-turn" -->\n'
        "```\n\n"
        '<!-- enforce: requires-skill-call="real-skill" trigger="real-trigger" scope="same-turn" -->\n',
    )
    markers = parse_markers(path)
    assert len(markers) == 1
    assert markers[0]["requires_skill_call"] == "real-skill"


def test_real_enforce_markers_doc_has_zero_live_markers():
    """The engine's own documentation of its syntax must not self-register
    as a rule."""
    assert parse_markers(str(ENFORCE_MARKERS_DOC)) == []
