#!/usr/bin/env python3
"""GraphRAG Dynamic Context Enrichment Engine (enrich_skill_context.py).

Bridges vector semantic search (skill-search / Qdrant) with the Labeled Property
Graph topology engine. Enriches search results and dynamic agent prompts with:
  - Direct prerequisites / dependencies (what must be invoked first)
  - Upstream callers / dependents (who relies on this skill)
  - Enterprise/Public equivalence pairs (PAIR_OF_INTERNAL)
  - Transitive blast radius (blast radius safety audit)
  - Community cluster peers (skills commonly bundled together)
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Set, Union

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from skill_graph_analyzer import SkillGraphAnalyzer
from extract_skill_graph import extract_skill_graph, PAIR_OF_INTERNAL_MAPPINGS

DEFAULT_GRAPH_CANDIDATES = [
    "/tmp/skills-graph.json",
    os.path.join(os.path.dirname(SCRIPT_DIR), "resources", "skill-graph.json"),
]


def _resolve_graph_data(graph_data_or_path: Union[Dict[str, Any], str, None] = None) -> Dict[str, Any]:
    """Resolve graph data from dict, file path, or default candidate paths."""
    if isinstance(graph_data_or_path, dict):
        return graph_data_or_path
    if isinstance(graph_data_or_path, str) and os.path.isfile(graph_data_or_path):
        with open(graph_data_or_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Check default candidate paths
    for cand in DEFAULT_GRAPH_CANDIDATES:
        if os.path.isfile(cand):
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

    # Fall back to live extraction if repo root skills directory exists
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
    skills_dir = os.path.join(repo_root, "skills")
    if os.path.isdir(skills_dir):
        return extract_skill_graph(skills_dir)

    return {"nodes": [], "edges": []}


def enrich_skill(
    skill_id: str,
    graph_data_or_path: Union[Dict[str, Any], str, None] = None
) -> Dict[str, Any]:
    """Enrich a single skill with its topological graph context."""
    graph_data = _resolve_graph_data(graph_data_or_path)
    analyzer = SkillGraphAnalyzer(graph_data)

    # Dependencies: skills that this skill points to
    dependencies = sorted(list(analyzer.adj.get(skill_id, set())))

    # Callers: skills that point to this skill
    callers = sorted(list(analyzer.rev_adj.get(skill_id, set())))

    # Blast radius
    impact = analyzer.calculate_blast_radius(skill_id)

    # Equivalence pair (bidirectional lookup)
    internal_pair = None
    if skill_id in PAIR_OF_INTERNAL_MAPPINGS:
        internal_pair = PAIR_OF_INTERNAL_MAPPINGS[skill_id]
    else:
        # Check reverse mapping
        for priv, pub in PAIR_OF_INTERNAL_MAPPINGS.items():
            if pub == skill_id:
                internal_pair = priv
                break

    # Cluster peers
    clusters = analyzer.detect_clusters()
    cluster_members: List[str] = []
    for c in clusters:
        if skill_id in c["members"]:
            cluster_members = [m for m in c["members"] if m != skill_id]
            break

    return {
        "skill_id": skill_id,
        "dependencies": dependencies,
        "callers": callers,
        "blast_radius": impact["total_affected"],
        "internal_pair": internal_pair,
        "cluster_members": cluster_members,
    }


def enrich_search_results(
    matches: List[Dict[str, Any]],
    graph_data_or_path: Union[Dict[str, Any], str, None] = None
) -> List[Dict[str, Any]]:
    """Enrich a list of search matches from skill-search with graph topology."""
    graph_data = _resolve_graph_data(graph_data_or_path)
    enriched = []
    for m in matches:
        item = dict(m)
        skill_name = item.get("skill_name")
        if skill_name:
            item["graph_context"] = enrich_skill(skill_name, graph_data)
        enriched.append(item)
    return enriched


def format_dynamic_context_banner(
    enriched_data: Union[Dict[str, Any], List[Dict[str, Any]]]
) -> str:
    """Format enriched graph data into a compact Markdown prompt injection banner."""
    if isinstance(enriched_data, dict) and "skill_id" in enriched_data:
        skill_id = enriched_data["skill_id"]
        deps = enriched_data.get("dependencies", [])
        callers = enriched_data.get("callers", [])
        blast = enriched_data.get("blast_radius", 0)
        pair = enriched_data.get("internal_pair")

        parts = [f"[Graph Context] Skill: {skill_id}"]
        if deps:
            parts.append(f"Dependencies: [{', '.join(deps)}]")
        if callers:
            parts.append(f"Callers: [{', '.join(callers)}]")
        parts.append(f"Blast Radius: {blast}")
        if pair:
            parts.append(f"Equivalence Pair: {pair}")
        return " | ".join(parts)

    if isinstance(enriched_data, list):
        lines = ["### GraphRAG Enriched Matches"]
        for m in enriched_data:
            sname = m.get("skill_name", "unknown")
            score = m.get("score", 0.0)
            g_ctx = m.get("graph_context", {})
            deps = g_ctx.get("dependencies", [])
            pair = g_ctx.get("internal_pair")
            blast = g_ctx.get("blast_radius", 0)

            line = f"- **{sname}** (score: {score:.4f}): Blast Radius {blast}"
            if deps:
                line += f", Depends on: [{', '.join(deps)}]"
            if pair:
                line += f", Equivalence: `{pair}`"
            lines.append(line)
        return "\n".join(lines)

    return ""


def main() -> None:
    """CLI Entrypoint."""
    parser = argparse.ArgumentParser(description="GraphRAG Dynamic Context Enrichment Engine")
    parser.add_argument("--skill", help="Single skill name to enrich")
    parser.add_argument("--input", "-i", help="Path to input LPG graph JSON file")
    parser.add_argument("--format", choices=["json", "banner"], default="json", help="Output format")
    args = parser.parse_args()

    if not args.skill:
        sys.stderr.write("ERROR: --skill is required\n")
        sys.exit(1)

    enriched = enrich_skill(args.skill, graph_data_or_path=args.input)

    if args.format == "banner":
        print(format_dynamic_context_banner(enriched))
    else:
        print(json.dumps(enriched, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
