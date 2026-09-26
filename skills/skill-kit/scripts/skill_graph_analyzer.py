#!/usr/bin/env python3
"""Skill Topology Graph Analyzer (skill_graph_analyzer.py).

Provides graph engineering analysis over skill dependency graphs:
  - Directed cycle detection (Tarjan/DFS DAG validation)
  - Transitive blast radius calculation (upstream dependent impact)
  - Topological metrics (in-degree, out-degree, centrality)
  - Community clustering (Louvain modularity / WCC) for plugin bundle recommendations
"""

import argparse
from collections import defaultdict, deque
import json
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Optional NetworkX acceleration
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


class SkillGraphAnalyzer:
    """Core analysis engine for Skill Topology Graphs."""

    def __init__(self, graph_data: Dict[str, Any]):
        """Initialize analyzer with canonical LPG dict containing nodes and edges."""
        self.raw_data = graph_data
        self.nodes = {n["id"]: n for n in graph_data.get("nodes", [])}
        self.edges = graph_data.get("edges", [])

        # Forward adjacency: source -> targets (source depends on target)
        self.adj: Dict[str, Set[str]] = defaultdict(set)
        # Reverse adjacency: target -> sources (sources that depend on target)
        self.rev_adj: Dict[str, Set[str]] = defaultdict(set)

        for edge in self.edges:
            src = edge["source"]
            tgt = edge["target"]
            self.adj[src].add(tgt)
            self.rev_adj[tgt].add(src)

        # Build NetworkX DiGraph if library is available
        self.nx_graph = None
        if HAS_NETWORKX:
            self.nx_graph = nx.DiGraph()
            for node_id, attrs in self.nodes.items():
                self.nx_graph.add_node(node_id, **attrs)
            for edge in self.edges:
                self.nx_graph.add_edge(
                    edge["source"],
                    edge["target"],
                    kind=edge.get("kind", "DEPENDS_ON"),
                    weight=edge.get("weight", 1.0)
                )

    def detect_cycles(self) -> List[List[str]]:
        """Detect directed cycles in the graph. Returns list of cycles."""
        if HAS_NETWORKX and self.nx_graph is not None:
            try:
                cycles = list(nx.simple_cycles(self.nx_graph))
                return cycles
            except Exception:
                pass  # Fall back to pure Python

        # Pure Python DFS cycle detection
        cycles: List[List[str]] = []
        visited: Dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited
        parent_map: Dict[str, str] = {}
        path: List[str] = []

        all_nodes = set(self.nodes.keys()).union(self.adj.keys()).union(self.rev_adj.keys())

        def dfs(u: str) -> None:
            visited[u] = 1
            path.append(u)
            for v in self.adj.get(u, ()):
                if visited.get(v, 0) == 1:
                    # Found back-edge u -> v
                    idx = path.index(v)
                    cycle = path[idx:] + [v]
                    cycles.append(cycle)
                elif visited.get(v, 0) == 0:
                    dfs(v)
            path.pop()
            visited[u] = 2

        for node in sorted(all_nodes):
            if visited.get(node, 0) == 0:
                dfs(node)

        return cycles

    def calculate_blast_radius(self, target: str) -> Dict[str, Any]:
        """Calculate the blast radius of modifying a target skill.
        
        Finds all skills that directly or transitively depend on target
        by traversing reverse dependency edges (incoming edges).
        """
        direct_dependents = sorted(list(self.rev_adj.get(target, set())))

        # BFS over reverse adjacency to find all transitive upstream dependents
        visited: Set[str] = set()
        queue: deque = deque(direct_dependents)
        for dep in direct_dependents:
            visited.add(dep)

        while queue:
            curr = queue.popleft()
            for parent in self.rev_adj.get(curr, ()):
                if parent not in visited and parent != target:
                    visited.add(parent)
                    queue.append(parent)

        transitive_dependents = sorted(list(visited))

        return {
            "target": target,
            "direct_dependents": direct_dependents,
            "transitive_dependents": transitive_dependents,
            "total_affected": len(transitive_dependents),
        }

    def get_node_metrics(self, node_id: str) -> Dict[str, Any]:
        """Return topological metrics for a specific skill node."""
        out_degree = len(self.adj.get(node_id, ()))
        in_degree = len(self.rev_adj.get(node_id, ()))

        betweenness = 0.0
        if HAS_NETWORKX and self.nx_graph is not None and len(self.nx_graph) > 0:
            try:
                bc_map = nx.betweenness_centrality(self.nx_graph, weight="weight")
                betweenness = bc_map.get(node_id, 0.0)
            except Exception:
                pass

        return {
            "id": node_id,
            "in_degree": in_degree,
            "out_degree": out_degree,
            "betweenness_centrality": betweenness,
        }

    def detect_clusters(self) -> List[Dict[str, Any]]:
        """Detect clusters/communities for plugin bundle recommendations."""
        # Method 1: Louvain community detection if NetworkX is available
        if HAS_NETWORKX and self.nx_graph is not None and len(self.nx_graph) > 0:
            try:
                undirected = self.nx_graph.to_undirected()
                communities = list(nx.community.louvain_communities(undirected, weight="weight", seed=42))
                result = []
                for i, comm in enumerate(communities):
                    result.append({
                        "cluster_id": i + 1,
                        "members": sorted(list(comm)),
                        "size": len(comm),
                    })
                return result
            except Exception:
                pass

        # Method 2: Pure Python Weakly Connected Components (WCC)
        undirected_adj: Dict[str, Set[str]] = defaultdict(set)
        for u in self.adj:
            for v in self.adj[u]:
                undirected_adj[u].add(v)
                undirected_adj[v].add(u)

        all_nodes = set(self.nodes.keys()).union(undirected_adj.keys())
        visited: Set[str] = set()
        clusters = []
        cluster_id = 1

        for node in sorted(all_nodes):
            if node not in visited:
                comp: Set[str] = set()
                q = deque([node])
                visited.add(node)
                while q:
                    curr = q.popleft()
                    comp.add(curr)
                    for nbr in undirected_adj.get(curr, ()):
                        if nbr not in visited:
                            visited.add(nbr)
                            q.append(nbr)
                clusters.append({
                    "cluster_id": cluster_id,
                    "members": sorted(list(comp)),
                    "size": len(comp),
                })
                cluster_id += 1

        return clusters


def detect_cycles(graph_data: Dict[str, Any]) -> List[List[str]]:
    """Helper functional API to detect cycles."""
    return SkillGraphAnalyzer(graph_data).detect_cycles()


def calculate_blast_radius(graph_data: Dict[str, Any], target: str) -> Dict[str, Any]:
    """Helper functional API to calculate blast radius."""
    return SkillGraphAnalyzer(graph_data).calculate_blast_radius(target)


def main() -> None:
    """CLI Entrypoint for skill graph analysis."""
    parser = argparse.ArgumentParser(description="Skill Topology Graph Analyzer")
    parser.add_argument("--input", "-i", required=True, help="Path to skill graph JSON file")
    parser.add_argument("--cycles", action="store_true", help="Detect cycles in dependency graph")
    parser.add_argument("--blast-radius", help="Calculate blast radius for a target skill")
    parser.add_argument("--clusters", action="store_true", help="Detect plugin clustering recommendations")
    parser.add_argument("--metrics", help="Output metrics for a specific skill, or 'all'")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        sys.stderr.write(f"ERROR: input graph file not found: {args.input}\n")
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    analyzer = SkillGraphAnalyzer(graph_data)

    if args.cycles:
        cycles = analyzer.detect_cycles()
        print(json.dumps({"cycle_count": len(cycles), "cycles": cycles}, indent=2, ensure_ascii=False))
        if cycles:
            sys.exit(1)  # Signal CI failure on cycle detection

    elif args.blast_radius:
        result = analyzer.calculate_blast_radius(args.blast_radius)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.clusters:
        clusters = analyzer.detect_clusters()
        print(json.dumps({"cluster_count": len(clusters), "clusters": clusters}, indent=2, ensure_ascii=False))

    elif args.metrics:
        if args.metrics == "all":
            all_metrics = [analyzer.get_node_metrics(nid) for nid in sorted(analyzer.nodes.keys())]
            print(json.dumps(all_metrics, indent=2, ensure_ascii=False))
        else:
            metrics = analyzer.get_node_metrics(args.metrics)
            print(json.dumps(metrics, indent=2, ensure_ascii=False))

    else:
        # Default: summary overview
        cycles = analyzer.detect_cycles()
        clusters = analyzer.detect_clusters()
        print(json.dumps({
            "node_count": len(analyzer.nodes),
            "edge_count": len(analyzer.edges),
            "cycle_count": len(cycles),
            "cluster_count": len(clusters),
        }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
