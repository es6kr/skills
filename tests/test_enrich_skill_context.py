"""Unit tests for enrich_skill_context.py (GraphRAG Dynamic Context Enrichment).

Tests:
  - Single skill enrichment with graph topology (dependencies, callers, blast radius, equivalence pair)
  - Batch search result enrichment (augmenting skill-search matches with graph context)
  - Dynamic context banner formatting for prompt injection
  - CLI execution outputting enriched JSON
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

from enrich_skill_context import (
    enrich_skill,
    enrich_search_results,
    format_dynamic_context_banner,
)


@pytest.fixture
def sample_graph():
    """Sample LPG graph data."""
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


def test_enrich_single_skill_dependencies_and_callers(sample_graph):
    """Verify single skill enrichment returns correct upstream and downstream topology."""
    cw_ctx = enrich_skill("code-workflow", sample_graph)
    assert cw_ctx["skill_id"] == "code-workflow"
    assert "tdd" in cw_ctx["dependencies"]
    assert len(cw_ctx["callers"]) == 0
    assert cw_ctx["blast_radius"] == 0

    tdd_ctx = enrich_skill("tdd", sample_graph)
    assert tdd_ctx["skill_id"] == "tdd"
    assert len(tdd_ctx["dependencies"]) == 0
    assert "code-workflow" in tdd_ctx["callers"]
    assert tdd_ctx["blast_radius"] == 1


def test_enrich_single_skill_internal_pair(sample_graph):
    """Verify enterprise/public equivalence pair is recognized."""
    plane_ctx = enrich_skill("plane", sample_graph)
    assert plane_ctx["internal_pair"] == "backlog"

    backlog_ctx = enrich_skill("backlog", sample_graph)
    assert backlog_ctx["internal_pair"] == "plane"


def test_enrich_search_results(sample_graph):
    """Verify batch search matches from skill-search are enriched with graph context."""
    search_matches = [
        {"skill_name": "code-workflow", "topic_file": "steps.md", "score": 0.89},
        {"skill_name": "plane", "topic_file": "sync.md", "score": 0.82},
    ]

    enriched = enrich_search_results(search_matches, sample_graph)
    assert len(enriched) == 2

    m0 = enriched[0]
    assert "graph_context" in m0
    assert "tdd" in m0["graph_context"]["dependencies"]

    m1 = enriched[1]
    assert "graph_context" in m1
    assert m1["graph_context"]["internal_pair"] == "backlog"


def test_format_dynamic_context_banner(sample_graph):
    """Verify dynamic prompt injection banner formatting."""
    cw_ctx = enrich_skill("code-workflow", sample_graph)
    banner = format_dynamic_context_banner(cw_ctx)

    assert "[Graph Context]" in banner
    assert "code-workflow" in banner
    assert "Dependencies: [tdd]" in banner


def test_cli_enrich_skill_context(sample_graph):
    """Verify CLI tool outputs valid enriched JSON."""
    script_path = os.path.join(SCRIPTS_DIR, "enrich_skill_context.py")
    with tempfile.TemporaryDirectory() as tmpdir:
        graph_file = os.path.join(tmpdir, "graph.json")
        with open(graph_file, "w", encoding="utf-8") as f:
            json.dump(sample_graph, f)

        proc = subprocess.run(
            [sys.executable, script_path, "--skill", "code-workflow", "--input", graph_file],
            capture_output=True,
            text=True
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert data["skill_id"] == "code-workflow"
        assert "tdd" in data["dependencies"]
