"""Unit tests for extract_skill_graph.py (Skill Topology Graph Extractor).

Tests:
  - Frontmatter depends-on extraction (bracket and list syntax)
  - Body Skill(...) invocation parsing
  - Slash command (/slash) cross-reference parsing
  - PAIR_OF_INTERNAL equivalence mapping (private vs public pairs)
  - Full directory extraction producing canonical LPG JSON schema
  - CLI entrypoint execution
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

from extract_skill_graph import (
    parse_frontmatter_depends_on,
    parse_body_skill_invocations,
    parse_slash_commands,
    extract_skill_graph,
    PAIR_OF_INTERNAL_MAPPINGS,
)


def test_parse_frontmatter_depends_on_bracket():
    """Verify parsing depends-on with inline bracket list syntax."""
    content = """---
name: test-skill
description: A test skill
depends-on: [task-plan, tdd]
---
# Test Skill
Body content here.
"""
    deps = parse_frontmatter_depends_on(content)
    assert deps == ["task-plan", "tdd"]


def test_parse_frontmatter_depends_on_yaml_list():
    """Verify parsing depends-on with multi-line YAML list syntax."""
    content = """---
name: test-skill
description: A test skill
depends-on:
  - task-flow
  - backlog
---
# Test Skill
Body content here.
"""
    deps = parse_frontmatter_depends_on(content)
    assert deps == ["task-flow", "backlog"]


def test_parse_body_skill_invocations():
    """Verify parsing Skill("<target>") calls from markdown body."""
    body = """# Guide
First invoke Skill("task-exec") to begin.
Then call Skill("task-exec", "implement") for details.
Later also invoke Skill("verify-evidence").
"""
    invocations = parse_body_skill_invocations(body)
    assert "task-exec" in invocations
    assert "verify-evidence" in invocations
    assert len(invocations) == 2  # Deduplicated targets


def test_parse_slash_commands():
    """Verify parsing /<command> references while ignoring file paths."""
    text = """# Workflow
Run /next after completing the step.
You can also use /fix-plan or /task-flow.
Do not match /usr/bin/node, /workspace/file.md, or http://example.com/foo.
"""
    commands = parse_slash_commands(text)
    assert "next" in commands
    assert "fix-plan" in commands
    assert "task-flow" in commands
    assert "usr" not in commands
    assert "workspace" not in commands


def test_pair_of_internal_mappings_contract():
    """Verify PAIR_OF_INTERNAL_MAPPINGS contains documented enterprise-to-public pairs."""
    assert isinstance(PAIR_OF_INTERNAL_MAPPINGS, dict)
    assert PAIR_OF_INTERNAL_MAPPINGS.get("plane") == "backlog"
    assert PAIR_OF_INTERNAL_MAPPINGS.get("commit-splitter") == "commit-tidy"


def test_extract_skill_graph_from_directory():
    """Verify complete graph extraction from mock skill directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_a_dir = os.path.join(tmpdir, "skill-a")
        skill_b_dir = os.path.join(tmpdir, "skill-b")
        os.makedirs(skill_a_dir)
        os.makedirs(skill_b_dir)

        skill_a_content = """---
name: skill-a
description: Skill A
depends-on: [skill-b]
---
# Skill A
Invokes Skill("skill-b") and /skill-b.
"""
        skill_b_content = """---
name: skill-b
description: Skill B
---
# Skill B
Leaf node skill.
"""
        with open(os.path.join(skill_a_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(skill_a_content)
        with open(os.path.join(skill_b_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(skill_b_content)

        graph = extract_skill_graph(tmpdir)

        # Check nodes
        node_ids = {n["id"] for n in graph["nodes"]}
        assert "skill-a" in node_ids
        assert "skill-b" in node_ids

        # Check edges
        edges = graph["edges"]
        dep_edge = next((e for e in edges if e["kind"] == "DEPENDS_ON"), None)
        assert dep_edge is not None
        assert dep_edge["source"] == "skill-a"
        assert dep_edge["target"] == "skill-b"
        assert dep_edge["weight"] == 3.0

        invoke_edge = next((e for e in edges if e["kind"] == "INVOKES_SKILL"), None)
        assert invoke_edge is not None
        assert invoke_edge["source"] == "skill-a"
        assert invoke_edge["target"] == "skill-b"
        assert invoke_edge["weight"] == 2.0

        slash_edge = next((e for e in edges if e["kind"] == "INVOKES_SLASH"), None)
        assert slash_edge is not None
        assert slash_edge["source"] == "skill-a"
        assert slash_edge["target"] == "skill-b"
        assert slash_edge["weight"] == 1.0


def test_cli_extract_skill_graph():
    """Verify CLI execution generates valid JSON output."""
    script_path = os.path.join(SCRIPTS_DIR, "extract_skill_graph.py")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_json = os.path.join(tmpdir, "graph.json")
        proc = subprocess.run(
            [sys.executable, script_path, "--skills-dir", os.path.join(REPO_ROOT, "skills"), "--output", out_json],
            capture_output=True,
            text=True
        )
        assert proc.returncode == 0
        assert os.path.isfile(out_json)
        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0
