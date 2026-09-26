#!/usr/bin/env python3
"""Interactive Skill Topology Graph Renderer (render_skill_graph.py).

Converts a canonical Labeled Property Graph (LPG) JSON into an interactive,
self-contained d3-force HTML visualizer.

Features:
  - Plugin and community group color clustering
  - Edge kind styling (thick, solid, dotted, outside)
  - Zoom, pan, and physics force tuning controls
  - Real-time search and blast radius highlighting
  - Edge weight filtering slider
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Set

# Curated palette for plugin/cluster groups
GROUP_PALETTES = [
    "#3b82f6",  # es6kr blue
    "#10b981",  # dgs emerald
    "#8b5cf6",  # superpowers violet
    "#f59e0b",  # amber
    "#ec4899",  # pink
    "#06b6d4",  # cyan
    "#f97316",  # orange
    "#64748b",  # slate
    "#6366f1",  # indigo
    "#14b8a6",  # teal
]


def convert_lpg_to_d3_schema(lpg_data: Dict[str, Any], title: str = "Skill Topology Graph") -> Dict[str, Any]:
    """Convert canonical LPG data into d3-force visualizer schema."""
    nodes = lpg_data.get("nodes", [])
    edges = lpg_data.get("edges", [])

    # Map groups
    group_map: Dict[str, Dict[str, str]] = {}
    known_plugins = sorted(list({n.get("plugin", "standalone") for n in nodes}))

    for i, plugin_name in enumerate(known_plugins):
        color = GROUP_PALETTES[i % len(GROUP_PALETTES)]
        group_map[plugin_name] = {
            "color": color,
            "label": plugin_name,
        }

    skill_hubs: List[Dict[str, Any]] = []
    node_ids: Set[str] = set()

    for n in nodes:
        nid = n["id"]
        node_ids.add(nid)
        plugin = n.get("plugin", "standalone")
        skill_hubs.append({
            "id": nid,
            "group": plugin,
            "label": nid,
            "type": n.get("type", "skill"),
        })

    links: List[Dict[str, Any]] = []
    for e in edges:
        src = e["source"]
        tgt = e["target"]
        kind = e.get("kind", "DEPENDS_ON")
        weight = float(e.get("weight", 1.0))

        # Translate LPG kind to d3 link style
        if kind == "DEPENDS_ON":
            d3_kind = "thick"
        elif kind == "INVOKES_SKILL":
            d3_kind = "solid"
        elif kind == "INVOKES_SLASH":
            d3_kind = "dotted"
        elif kind == "PAIR_OF_INTERNAL":
            d3_kind = "thick"
        else:
            d3_kind = "solid"

        # Check if outside target
        if tgt not in node_ids:
            d3_kind = "outside"

        links.append({
            "source": src,
            "target": tgt,
            "weight": weight,
            "kind": d3_kind,
            "note": f"{src} -> {tgt} ({kind})",
        })

    return {
        "title": title,
        "subtitle": "Interactive d3-force Skill Topology Graph",
        "groups": group_map,
        "skillHubs": skill_hubs,
        "topics": [],
        "links": links,
    }


def generate_standalone_html(d3_data: Dict[str, Any]) -> str:
    """Generate self-contained HTML containing embedded D3 and interactive UI."""
    data_json = json.dumps(d3_data, indent=2, ensure_ascii=False)
    title = d3_data.get("title", "Skill Topology Graph")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script src="https://d3js.org/d3.v7.min.js"></script>
  <style>
    :root {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #38bdf8;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      height: 100vh;
      overflow: hidden;
    }}
    #sidebar {{
      width: 320px;
      background: var(--card-bg);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      padding: 1.25rem;
      gap: 1.25rem;
      z-index: 10;
      overflow-y: auto;
    }}
    #graph-container {{
      flex: 1;
      position: relative;
    }}
    svg {{
      width: 100%;
      height: 100%;
    }}
    h1 {{ font-size: 1.15rem; font-weight: 700; color: #fff; }}
    .subtitle {{ font-size: 0.8rem; color: var(--muted); }}
    .control-group {{
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }}
    label {{
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    input[type="text"] {{
      width: 100%;
      padding: 0.5rem 0.75rem;
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 0.375rem;
      color: var(--text);
      font-size: 0.875rem;
    }}
    input[type="text"]:focus {{
      outline: none;
      border-color: var(--accent);
    }}
    input[type="range"] {{
      width: 100%;
      accent-color: var(--accent);
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.85rem;
      cursor: pointer;
    }}
    .legend-color {{
      width: 12px;
      height: 12px;
      border-radius: 3px;
    }}
    #node-details {{
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 0.375rem;
      padding: 0.75rem;
      font-size: 0.8rem;
      display: none;
    }}
    .link {{
      stroke-opacity: 0.6;
    }}
    .link-thick {{ stroke-width: 3px; }}
    .link-solid {{ stroke-width: 1.5px; }}
    .link-dotted {{ stroke-dasharray: 4,4; stroke-width: 1.5px; stroke-opacity: 0.4; }}
    .link-outside {{ stroke: #f97316; stroke-dasharray: 2,2; stroke-width: 2px; }}
    .node text {{
      font-size: 11px;
      font-weight: 600;
      fill: #f8fafc;
      pointer-events: none;
      text-shadow: 0 1px 3px rgba(0,0,0,0.8);
    }}
    .node rect {{
      stroke: #fff;
      stroke-width: 1.5px;
      cursor: grab;
      rx: 4px;
      ry: 4px;
    }}
    .highlighted rect {{
      stroke: #facc15 !important;
      stroke-width: 3px !important;
      filter: drop-shadow(0 0 6px #facc15);
    }}
    .dimmed {{
      opacity: 0.15;
    }}
  </style>
</head>
<body>
  <div id="sidebar">
    <div>
      <h1>{title}</h1>
      <p class="subtitle">{d3_data.get("subtitle", "")}</p>
    </div>

    <div class="control-group">
      <label for="search-box">Search & Blast Radius</label>
      <input type="text" id="search-box" placeholder="e.g. tdd, code-workflow">
    </div>

    <div class="control-group">
      <label>Edge Weight Filter (<span id="weight-val">1.0</span>+)</label>
      <input type="range" id="weight-slider" min="1" max="5" step="0.5" value="1">
    </div>

    <div class="control-group">
      <label>Plugin Groups</label>
      <div id="legend-list"></div>
    </div>

    <div id="node-details">
      <label>Selected Node</label>
      <div id="details-content" style="margin-top: 0.5rem; line-height: 1.5;"></div>
    </div>
  </div>

  <div id="graph-container">
    <svg id="graph-svg"></svg>
  </div>

  <script>
    const graphData = {data_json};

    const svg = d3.select("#graph-svg");
    const container = svg.append("g");

    const width = document.getElementById("graph-container").clientWidth || 1000;
    const height = document.getElementById("graph-container").clientHeight || 800;

    // Zoom setup
    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => container.attr("transform", event.transform));
    svg.call(zoom);

    // Build legend
    const legendList = document.getElementById("legend-list");
    Object.entries(graphData.groups).forEach(([grp, info]) => {{
      const div = document.createElement("div");
      div.className = "legend-item";
      div.innerHTML = `<span class="legend-color" style="background: ${{info.color}}"></span><span>${{info.label}}</span>`;
      legendList.appendChild(div);
    }});

    // Nodes & Links mapping
    const nodeMap = new Map();
    const nodes = graphData.skillHubs.map(h => {{
      const node = {{ id: h.id, group: h.group, label: h.label }};
      nodeMap.set(h.id, node);
      return node;
    }});

    // Filter valid links
    const links = graphData.links.filter(l => nodeMap.has(l.source) && nodeMap.has(l.target)).map(l => ({{
      source: l.source,
      target: l.target,
      weight: l.weight,
      kind: l.kind,
      note: l.note
    }}));

    // Force simulation
    const simulation = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id(d => d.id).distance(d => 140 - (d.weight * 15)).strength(0.5))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide(45));

    // Render links
    const link = container.append("g")
      .attr("class", "links")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("class", d => `link link-${{d.kind}}`)
      .attr("stroke", d => d.kind === "outside" ? "#f97316" : "#64748b");

    // Render nodes
    const node = container.append("g")
      .attr("class", "nodes")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .attr("class", "node")
      .call(d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended));

    node.append("rect")
      .attr("width", d => Math.max(70, d.label.length * 8 + 16))
      .attr("height", 28)
      .attr("x", d => -Math.max(70, d.label.length * 8 + 16) / 2)
      .attr("y", -14)
      .attr("fill", d => graphData.groups[d.group]?.color || "#64748b");

    node.append("text")
      .attr("text-anchor", "middle")
      .attr("dy", 4)
      .text(d => d.label);

    node.on("click", (event, d) => {{
      event.stopPropagation();
      selectNode(d.id);
    }});

    svg.on("click", () => {{
      clearSelection();
    }});

    simulation.on("tick", () => {{
      link
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);

      node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
    }});

    function dragstarted(event, d) {{
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }}
    function dragged(event, d) {{
      d.fx = event.x;
      d.fy = event.y;
    }}
    function dragended(event, d) {{
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }}

    // Search & Blast Radius
    const searchBox = document.getElementById("search-box");
    searchBox.addEventListener("input", (e) => {{
      const val = e.target.value.trim().toLowerCase();
      if (!val) {{
        clearSelection();
        return;
      }}
      const match = nodes.find(n => n.id.toLowerCase().includes(val));
      if (match) selectNode(match.id);
    }});

    // Weight slider
    const slider = document.getElementById("weight-slider");
    const weightVal = document.getElementById("weight-val");
    slider.addEventListener("input", (e) => {{
      const minW = parseFloat(e.target.value);
      weightVal.textContent = minW.toFixed(1);
      link.style("display", d => d.weight >= minW ? "block" : "none");
    }});

    function selectNode(nodeId) {{
      const connected = new Set([nodeId]);
      links.forEach(l => {{
        const sId = typeof l.source === "object" ? l.source.id : l.source;
        const tId = typeof l.target === "object" ? l.target.id : l.target;
        if (sId === nodeId) connected.add(tId);
        if (tId === nodeId) connected.add(sId);
      }});

      node.classed("highlighted", d => d.id === nodeId);
      node.classed("dimmed", d => !connected.has(d.id));
      link.classed("dimmed", l => {{
        const sId = typeof l.source === "object" ? l.source.id : l.source;
        const tId = typeof l.target === "object" ? l.target.id : l.target;
        return !(sId === nodeId || tId === nodeId);
      }});

      // Show details
      const details = document.getElementById("node-details");
      const content = document.getElementById("details-content");
      details.style.display = "block";
      const targetNode = nodes.find(n => n.id === nodeId);
      content.innerHTML = `
        <strong>${{nodeId}}</strong><br>
        Group: ${{targetNode?.group}}<br>
        Connected: ${{connected.size - 1}} skills
      `;
    }}

    function clearSelection() {{
      node.classed("highlighted", false).classed("dimmed", false);
      link.classed("dimmed", false);
      document.getElementById("node-details").style.display = "none";
    }}
  </script>
</body>
</html>
"""


def render_skill_graph(input_path: str, output_path: str, title: Optional[str] = None) -> None:
    """Read LPG JSON and write standalone HTML."""
    with open(input_path, "r", encoding="utf-8") as f:
        lpg_data = json.load(f)

    doc_title = title or "Skill Topology Graph"
    d3_data = convert_lpg_to_d3_schema(lpg_data, title=doc_title)
    html_content = generate_standalone_html(d3_data)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)


def main() -> None:
    """CLI Entrypoint for skill graph rendering."""
    parser = argparse.ArgumentParser(description="Skill Topology Graph HTML Renderer")
    parser.add_argument("--input", "-i", required=True, help="Path to input LPG graph JSON")
    parser.add_argument("--output", "-o", required=True, help="Path to output HTML file")
    parser.add_argument("--title", "-t", default="Skill Topology Graph", help="Document title")
    args = parser.parse_args()

    render_skill_graph(args.input, args.output, title=args.title)
    print(f"Successfully generated skill graph HTML: {args.output}")


if __name__ == "__main__":
    main()
