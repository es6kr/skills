#!/usr/bin/env python3
"""LLM-Wiki Skill Topology Bridge (sync_wiki_graph.py).

Synchronizes computed skill topology graph metrics, cycle audits, and
blast radius rankings into LLM-Wiki knowledge pages (pages/ops/skill-topology-matrix.md).

Ensures:
  - Strict YAML frontmatter schema compliance (created, last_modified, language: en)
  - Existing created date preservation
  - Dual-SSOT preservation: Graph is an analytical projection; Wiki is the knowledge layer.
"""

import argparse
from datetime import date
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

# Import local analyzer
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from skill_graph_analyzer import SkillGraphAnalyzer
from extract_skill_graph import PAIR_OF_INTERNAL_MAPPINGS


def _extract_existing_created_date(file_path: str) -> Optional[str]:
    """Extract existing created date from markdown frontmatter."""
    if not os.path.isfile(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read(2048)  # Read frontmatter header
        match = re.search(r"^created:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    return None


def generate_wiki_matrix_markdown(
    graph_data: Dict[str, Any],
    created_date: Optional[str] = None,
    last_modified_date: Optional[str] = None
) -> str:
    """Generate Markdown document for pages/ops/skill-topology-matrix.md."""
    today_str = date.today().isoformat()
    init_date = created_date or today_str

    analyzer = SkillGraphAnalyzer(graph_data)
    cycles = analyzer.detect_cycles()
    clusters = analyzer.detect_clusters()

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    # Calculate metrics for all nodes
    node_stats: List[Dict[str, Any]] = []
    for n in nodes:
        nid = n["id"]
        plugin = n.get("plugin", "standalone")
        metrics = analyzer.get_node_metrics(nid)
        impact = analyzer.calculate_blast_radius(nid)
        node_stats.append({
            "id": nid,
            "plugin": plugin,
            "in_degree": metrics["in_degree"],
            "out_degree": metrics["out_degree"],
            "blast_radius": impact["total_affected"],
        })

    # Sort by blast_radius desc, then in_degree desc
    node_stats.sort(key=lambda x: (x["blast_radius"], x["in_degree"]), reverse=True)

    # Build frontmatter
    fm_lines = [
        "---",
        "title: Skill Topology Matrix",
        f"created: {init_date}",
    ]
    if last_modified_date:
        fm_lines.append(f"last_modified: {last_modified_date}")
    elif created_date and created_date != today_str:
        fm_lines.append(f"last_modified: {today_str}")

    meta_banner = f"> **Document Metadata**: Initial created date: {init_date}"
    if last_modified_date or (created_date and created_date != today_str):
        mod_date = last_modified_date or today_str
        meta_banner += f" / Last modified date: {mod_date}"
    meta_banner += " / Status: Synchronized from Canonical Graph"

    fm_lines.extend([
        "language: en",
        "category: ops",
        "relates_to:",
        '  - "es6kr/llm-wiki/pages/decision/graph-engineering-github-flow-fit.md"',
        '  - "daegunsoftDev/llm-wiki/pages/ops/skill-pairing-internal-vs-clawhub.md"',
        "---",
        "",
        meta_banner,
        "",
        "# Skill Topology Matrix",
        "",
        "This document is automatically projected from the canonical skill topology graph.",
        "It provides architectural visibility into skill dependencies, cycle warnings, and blast radius impact.",
        "",
        "## 1. Topological Summary",
        "",
        "| Metric | Measured Value | Architectural Invariant |",
        "|:---|:---:|:---|",
        f"| **Total Skill Nodes** | `{len(nodes)}` | Discovered standalone and plugin skills |",
        f"| **Total Dependency Edges** | `{len(edges)}` | Labeled Property Graph (LPG) connections |",
        f"| **Detected Cycles** | `{len(cycles)}` | {'⚠️ Circular dependencies require attention' if cycles else '✅ Clean DAG (0 cycles)'} |",
        f"| **Plugin Clusters** | `{len(clusters)}` | Modularity / connected community groupings |",
        "",
        "## 2. High-Impact Skills Ranking",
        "",
        "Skills ranked by blast radius (number of transitive upstream dependents that break if this skill is modified):",
        "",
        "| Rank | Skill ID | Plugin Bundle | In-Degree (Direct Dependents) | Out-Degree (Dependencies) | Blast Radius (Total Affected) |",
        "|:---:|:---|:---:|:---:|:---:|:---:|",
    ])

    for rank, stat in enumerate(node_stats[:15], 1):
        fm_lines.append(
            f"| {rank} | `{stat['id']}` | `{stat['plugin']}` | {stat['in_degree']} | {stat['out_degree']} | **{stat['blast_radius']}** |"
        )

    fm_lines.extend([
        "",
        "## 3. Plugin Clusters and Equivalence Pairs",
        "",
        "### Enterprise / Public Equivalence Mappings (`PAIR_OF_INTERNAL`)",
        "",
        "| Enterprise Skill (Private) | ClawHub Distribution (Public) | Equivalence Role |",
        "|:---|:---|:---|",
    ])

    for priv, pub in sorted(PAIR_OF_INTERNAL_MAPPINGS.items()):
        fm_lines.append(f"| `{priv}` | `{pub}` | Internal enterprise tracker vs OSS distribution |")

    fm_lines.extend([
        "",
        "### Community Clusters (Louvain / WCC)",
        "",
        "| Cluster ID | Size | Representative Members |",
        "|:---:|:---:|:---|",
    ])

    for c in clusters[:10]:
        cid = c["cluster_id"]
        size = c["size"]
        sample_members = ", ".join([f"`{m}`" for m in c["members"][:5]])
        if size > 5:
            sample_members += f" *(+{size - 5} more)*"
        fm_lines.append(f"| Cluster {cid} | {size} | {sample_members} |")

    fm_lines.extend([
        "",
        "## 4. Architectural Guidelines",
        "",
        "- **Projection-Only Policy**: This wiki page is an analytical projection derived from `SKILL.md` frontmatter and code.",
        "- **Zero Circular Invocations**: Maintain DAG topology by refactoring high-centrality hub skills into modular topics.",
        "- **Blast Radius Safety**: Before modifying skills with Blast Radius $\\ge 5$, run `python3 skills/skill-kit/scripts/skill_graph_analyzer.py --blast-radius <skill>` to audit affected callers.",
        ""
    ])

    return "\n".join(fm_lines)


def sync_wiki_matrix(graph_data: Dict[str, Any], wiki_dir: str) -> str:
    """Write skill topology matrix to target wiki pages/ops/ directory."""
    ops_dir = os.path.join(wiki_dir, "pages", "ops")
    os.makedirs(ops_dir, exist_ok=True)
    target_file = os.path.join(ops_dir, "skill-topology-matrix.md")

    existing_created = _extract_existing_created_date(target_file)
    last_mod = date.today().isoformat() if existing_created else None

    md_content = generate_wiki_matrix_markdown(
        graph_data,
        created_date=existing_created,
        last_modified_date=last_mod
    )

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(md_content)

    return target_file


def main() -> None:
    """CLI Entrypoint."""
    parser = argparse.ArgumentParser(description="LLM-Wiki Skill Topology Bridge")
    parser.add_argument("--input", "-i", required=True, help="Path to input LPG graph JSON")
    parser.add_argument("--wiki-dir", "-w", required=True, help="Path to wiki root directory")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        sys.stderr.write(f"ERROR: input file not found: {args.input}\n")
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    target_path = sync_wiki_matrix(graph_data, os.path.abspath(args.wiki_dir))
    print(f"Successfully synchronized topology matrix to: {target_path}")


if __name__ == "__main__":
    main()
