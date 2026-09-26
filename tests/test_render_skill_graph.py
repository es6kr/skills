"""Unit tests for render_skill_graph.py (Interactive d3-force visualizer).

Tests:
  - Conversion from LPG schema to d3-force visualizer schema
  - Standalone HTML generation with embedded D3 controls
  - Cluster grouping and edge kind translation
  - CLI execution outputting self-contained HTML
"""
import json
import os
import subprocess
import sys
import tempfile
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "skills", "skill-kit", "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from render_skill_graph import (
    convert_lpg_to_d3_schema,
    generate_standalone_html,
    render_skill_graph,
)


@pytest.fixture
def sample_lpg():
    """Sample Labeled Property Graph."""
    return {
        "nodes": [
            {"id": "tdd", "type": "skill", "plugin": "es6kr"},
            {"id": "code-workflow", "type": "skill", "plugin": "es6kr"},
            {"id": "plane", "type": "skill", "plugin": "dgs"},
            {"id": "backlog", "type": "skill", "plugin": "es6kr"},
        ],
        "edges": [
            {"source": "code-workflow", "target": "tdd", "kind": "DEPENDS_ON", "weight": 3.0},
            {"source": "plane", "target": "backlog", "kind": "PAIR_OF_INTERNAL", "weight": 4.0},
        ],
    }


def test_convert_lpg_to_d3_schema(sample_lpg):
    """Verify conversion of LPG data into d3-force compatible schema."""
    d3_data = convert_lpg_to_d3_schema(sample_lpg, title="Test Skill Graph")

    assert d3_data["title"] == "Test Skill Graph"
    assert "groups" in d3_data
    assert "es6kr" in d3_data["groups"]
    assert "dgs" in d3_data["groups"]

    # Verify skill hubs
    hub_ids = {h["id"] for h in d3_data["skillHubs"]}
    assert "tdd" in hub_ids
    assert "code-workflow" in hub_ids
    assert "plane" in hub_ids
    assert "backlog" in hub_ids

    # Verify links
    assert len(d3_data["links"]) == 2
    dep_link = next(l for l in d3_data["links"] if l["source"] == "code-workflow")
    assert dep_link["target"] == "tdd"
    assert dep_link["weight"] == 3.0
    assert dep_link["kind"] == "thick"  # DEPENDS_ON translates to thick line


def test_generate_standalone_html(sample_lpg):
    """Verify HTML generation produces self-contained, valid HTML."""
    d3_data = convert_lpg_to_d3_schema(sample_lpg)
    html = generate_standalone_html(d3_data)

    assert "<!DOCTYPE html>" in html
    assert "<svg" in html
    assert "<script" in html
    assert "d3" in html
    assert "tdd" in html
    assert "code-workflow" in html
    assert len(html) > 1000


def test_cli_render_skill_graph(sample_lpg):
    """Verify CLI command renders HTML file to disk."""
    script_path = os.path.join(SCRIPTS_DIR, "render_skill_graph.py")
    with tempfile.TemporaryDirectory() as tmpdir:
        input_json = os.path.join(tmpdir, "graph.json")
        output_html = os.path.join(tmpdir, "graph.html")
        with open(input_json, "w", encoding="utf-8") as f:
            json.dump(sample_lpg, f)

        proc = subprocess.run(
            [sys.executable, script_path, "--input", input_json, "--output", output_html],
            capture_output=True,
            text=True
        )
        assert proc.returncode == 0
        assert os.path.isfile(output_html)
        with open(output_html, "r", encoding="utf-8") as f:
            content = f.read()
        assert "<!DOCTYPE html>" in content
        assert "tdd" in content
