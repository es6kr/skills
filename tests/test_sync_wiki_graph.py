"""Unit tests for sync_wiki_graph.py (LLM-Wiki Topology Bridge).

Tests:
  - Markdown topology matrix page generation with valid YAML frontmatter
  - Frontmatter created date preservation and last_modified updates
  - Impact ranking and cluster breakdown tables
  - CLI execution writing to target wiki pages/ops/ directory
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

from sync_wiki_graph import (
    generate_wiki_matrix_markdown,
    sync_wiki_matrix,
)


@pytest.fixture
def sample_graph_data():
    """Sample LPG graph data with analysis results."""
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


def test_generate_wiki_matrix_markdown(sample_graph_data):
    """Verify markdown generator produces valid YAML frontmatter and tables."""
    md = generate_wiki_matrix_markdown(sample_graph_data)

    assert md.startswith("---\n")
    assert "title: Skill Topology Matrix" in md
    assert "created:" in md
    assert "language: en" in md
    assert "## 1. Topological Summary" in md
    assert "## 2. High-Impact Skills Ranking" in md
    assert "## 3. Plugin Clusters and Equivalence Pairs" in md
    assert "tdd" in md
    assert "code-workflow" in md


def test_sync_wiki_matrix_creates_file(sample_graph_data):
    """Verify sync_wiki_matrix writes to pages/ops/skill-topology-matrix.md."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ops_dir = os.path.join(tmpdir, "pages", "ops")
        os.makedirs(ops_dir)

        target_file = sync_wiki_matrix(sample_graph_data, tmpdir)
        assert os.path.isfile(target_file)
        assert os.path.basename(target_file) == "skill-topology-matrix.md"

        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "title: Skill Topology Matrix" in content


def test_sync_wiki_matrix_preserves_created_date(sample_graph_data):
    """Verify existing created date is preserved while last_modified is updated."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ops_dir = os.path.join(tmpdir, "pages", "ops")
        os.makedirs(ops_dir)
        target_path = os.path.join(ops_dir, "skill-topology-matrix.md")

        # Initial file authored on an earlier date
        initial_content = """---
title: Skill Topology Matrix
created: 2026-08-01
language: en
---
# Old Content
"""
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(initial_content)

        sync_wiki_matrix(sample_graph_data, tmpdir)

        with open(target_path, "r", encoding="utf-8") as f:
            updated = f.read()

        assert "created: 2026-08-01" in updated
        assert "last_modified:" in updated


def test_cli_sync_wiki_graph(sample_graph_data):
    """Verify CLI tool execution."""
    script_path = os.path.join(SCRIPTS_DIR, "sync_wiki_graph.py")
    with tempfile.TemporaryDirectory() as tmpdir:
        input_json = os.path.join(tmpdir, "graph.json")
        wiki_dir = os.path.join(tmpdir, "wiki")
        os.makedirs(os.path.join(wiki_dir, "pages", "ops"))

        with open(input_json, "w", encoding="utf-8") as f:
            json.dump(sample_graph_data, f)

        proc = subprocess.run(
            [sys.executable, script_path, "--input", input_json, "--wiki-dir", wiki_dir],
            capture_output=True,
            text=True
        )
        assert proc.returncode == 0
        expected_output = os.path.join(wiki_dir, "pages", "ops", "skill-topology-matrix.md")
        assert os.path.isfile(expected_output)
