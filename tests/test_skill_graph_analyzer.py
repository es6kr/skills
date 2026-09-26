"""Unit tests for skill_graph_analyzer.py (Skill Topology Analyzer).

Tests:
  - Cycle detection in skill dependency graphs (DAG validation)
  - Transitive blast radius calculation (upstream dependent impact)
  - Topological metrics (in-degree, out-degree, centrality)
  - Cluster / community detection for plugin bundling
  - CLI analysis entrypoint execution
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

from skill_graph_analyzer import (
    SkillGraphAnalyzer,
    detect_cycles,
    calculate_blast_radius,
)


@pytest.fixture
def sample_dag():
    """Sample acyclic graph."""
    return {
        "nodes": [
            {"id": "tdd", "type": "skill", "plugin": "es6kr"},
            {"id": "task-exec", "type": "skill", "plugin": "es6kr"},
            {"id": "task-flow", "type": "skill", "plugin": "es6kr"},
            {"id": "code-workflow", "type": "skill", "plugin": "es6kr"},
            {"id": "unrelated", "type": "skill", "plugin": "es6kr"},
        ],
        "edges": [
            {"source": "task-exec", "target": "tdd", "kind": "DEPENDS_ON", "weight": 3.0},
            {"source": "task-flow", "target": "task-exec", "kind": "DEPENDS_ON", "weight": 3.0},
            {"source": "code-workflow", "target": "task-flow", "kind": "DEPENDS_ON", "weight": 3.0},
        ],
    }


@pytest.fixture
def cyclic_graph():
    """Sample graph containing a directed cycle A -> B -> C -> A."""
    return {
        "nodes": [
            {"id": "a", "type": "skill", "plugin": "standalone"},
            {"id": "b", "type": "skill", "plugin": "standalone"},
            {"id": "c", "type": "skill", "plugin": "standalone"},
            {"id": "d", "type": "skill", "plugin": "standalone"},
        ],
        "edges": [
            {"source": "a", "target": "b", "kind": "DEPENDS_ON", "weight": 3.0},
            {"source": "b", "target": "c", "kind": "INVOKES_SKILL", "weight": 2.0},
            {"source": "c", "target": "a", "kind": "INVOKES_SLASH", "weight": 1.0},
            {"source": "d", "target": "a", "kind": "DEPENDS_ON", "weight": 3.0},
        ],
    }


def test_detect_cycles_none_in_dag(sample_dag):
    """Verify DAG reports 0 cycles."""
    analyzer = SkillGraphAnalyzer(sample_dag)
    cycles = analyzer.detect_cycles()
    assert len(cycles) == 0


def test_detect_cycles_in_cyclic_graph(cyclic_graph):
    """Verify directed cycle A -> B -> C -> A is detected."""
    analyzer = SkillGraphAnalyzer(cyclic_graph)
    cycles = analyzer.detect_cycles()
    assert len(cycles) >= 1
    # Check that cycle elements contain a, b, c
    cycle_nodes = set()
    for cycle in cycles:
        cycle_nodes.update(cycle)
    assert {"a", "b", "c"}.issubset(cycle_nodes)
    assert "d" not in cycle_nodes  # d is an external dependent, not in the cycle


def test_calculate_blast_radius_single_source(sample_dag):
    """Verify blast radius computes transitive upstream dependents.
    
    If 'tdd' changes:
    - Direct dependent: task-exec (depends on tdd)
    - Transitive dependents: task-flow (depends on task-exec), code-workflow (depends on task-flow)
    - Unaffected: unrelated
    """
    analyzer = SkillGraphAnalyzer(sample_dag)
    impact = analyzer.calculate_blast_radius("tdd")

    assert impact["target"] == "tdd"
    assert set(impact["direct_dependents"]) == {"task-exec"}
    assert set(impact["transitive_dependents"]) == {"task-exec", "task-flow", "code-workflow"}
    assert "unrelated" not in impact["transitive_dependents"]
    assert impact["total_affected"] == 3


def test_calculate_blast_radius_leaf_node(sample_dag):
    """Verify blast radius for a top-level orchestrator with 0 dependents."""
    analyzer = SkillGraphAnalyzer(sample_dag)
    impact = analyzer.calculate_blast_radius("code-workflow")

    assert impact["target"] == "code-workflow"
    assert len(impact["direct_dependents"]) == 0
    assert len(impact["transitive_dependents"]) == 0
    assert impact["total_affected"] == 0


def test_topological_metrics(sample_dag):
    """Verify in-degree, out-degree, and centrality scores."""
    analyzer = SkillGraphAnalyzer(sample_dag)
    metrics = analyzer.get_node_metrics("task-exec")

    # In our graph, edges are (source, target) where source depends on target:
    # task-exec -> tdd (out-degree 1)
    # task-flow -> task-exec (in-degree 1)
    assert metrics["out_degree"] == 1  # depends on 1 skill
    assert metrics["in_degree"] == 1   # 1 skill depends on it


def test_community_detection(sample_dag):
    """Verify clustering groups connected nodes into coherent bundles."""
    analyzer = SkillGraphAnalyzer(sample_dag)
    clusters = analyzer.detect_clusters()
    assert isinstance(clusters, list)
    assert len(clusters) >= 1
    # Main workflow skills should be in the same cluster
    workflow_cluster = next((c for c in clusters if "tdd" in c["members"]), None)
    assert workflow_cluster is not None
    assert "task-exec" in workflow_cluster["members"]


def test_cli_skill_graph_analyzer(sample_dag):
    """Verify CLI execution for cycle detection and blast radius."""
    script_path = os.path.join(SCRIPTS_DIR, "skill_graph_analyzer.py")
    with tempfile.TemporaryDirectory() as tmpdir:
        input_json = os.path.join(tmpdir, "input.json")
        with open(input_json, "w", encoding="utf-8") as f:
            json.dump(sample_dag, f)

        # Test blast radius CLI
        proc = subprocess.run(
            [sys.executable, script_path, "--input", input_json, "--blast-radius", "tdd"],
            capture_output=True,
            text=True
        )
        assert proc.returncode == 0
        output = json.loads(proc.stdout)
        assert output["target"] == "tdd"
        assert output["total_affected"] == 3
