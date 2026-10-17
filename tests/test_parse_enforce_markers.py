"""Unit tests for parse_enforce_markers.parse_markers()."""
from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "skills" / "hook-kit" / "scripts" / "parse_enforce_markers.py"

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


def test_parses_requires_skill_call_marker(tmp_path):
    path = _write(
        tmp_path,
        "collect.md",
        '<!-- enforce: requires-skill-call="superpowers:receiving-code-review" '
        'trigger="before-dispatch" scope="same-turn" -->\n'
        "## Step 3.6\n",
    )
    markers = parse_markers(path)
    assert len(markers) == 1
    assert markers[0]["requires_skill_call"] == "superpowers:receiving-code-review"
    assert markers[0]["trigger"] == "before-dispatch"
    assert markers[0]["scope"] == "same-turn"
    assert markers[0]["source_skill"] == "fake-skill"


def test_parses_on_completion_marker(tmp_path):
    path = _write(
        tmp_path,
        "qdrant-import.md",
        '<!-- enforce: on-completion="qdrant-import success" '
        'requires-skill-call="next" scope="next-turn" -->\n',
    )
    markers = parse_markers(path)
    assert len(markers) == 1
    assert markers[0]["on_completion"] == "qdrant-import success"
    assert markers[0]["requires_skill_call"] == "next"
    assert markers[0]["scope"] == "next-turn"


def test_malformed_marker_is_skipped_not_raised(tmp_path):
    path = _write(
        tmp_path,
        "broken.md",
        '<!-- enforce: requires-skill-call="x" -->\n',  # missing scope=
    )
    markers = parse_markers(path)
    assert markers == []
    assert "missing scope" in parse_markers.last_errors[-1]


def test_two_markers_same_trigger_both_kept(tmp_path):
    path = _write(
        tmp_path,
        "double.md",
        '<!-- enforce: requires-skill-call="a" trigger="t" scope="same-turn" -->\n'
        '<!-- enforce: requires-skill-call="b" trigger="t" scope="same-turn" -->\n',
    )
    markers = parse_markers(path)
    assert len(markers) == 2
    assert {m["requires_skill_call"] for m in markers} == {"a", "b"}
