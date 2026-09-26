#!/usr/bin/env python3
"""Skill Topology Graph Extractor (extract_skill_graph.py).

Extracts a canonical Labeled Property Graph (LPG) from skill markdown definitions.
Captures:
  - Frontmatter `depends-on` (inline [a, b] and YAML list) -> DEPENDS_ON (weight: 3.0)
  - Body `Skill("<name>", ...)` calls -> INVOKES_SKILL (weight: 2.0)
  - Body `/<slash>` command references -> INVOKES_SLASH (weight: 1.0)
  - Enterprise/Public equivalence pairs -> PAIR_OF_INTERNAL (weight: 4.0)

Output schema:
{
  "nodes": [{"id": "<skill>", "type": "skill", "plugin": "<plugin|standalone>"}],
  "edges": [{"source": "<src>", "target": "<tgt>", "kind": "<KIND>", "weight": <float>}]
}
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Known equivalence pairs between private enterprise skills and public ClawHub skills
PAIR_OF_INTERNAL_MAPPINGS: Dict[str, str] = {
    "plane": "backlog",
    "commit-splitter": "commit-tidy",
    "ask": "doc-reorganizer",
    "wip": "backlog",
    "sync": "ai-config-sync",
}

# Directories and paths to exclude from slash command matching
PATH_EXCLUSIONS: Set[str] = {
    "usr", "bin", "workspace", "docs", "home", "mnt", "etc", "var", "tmp",
    "dev", "run", "sys", "opt", "lib", "root", "proc", "Users", "raw",
    "pages", "scripts", "skills", "plugins", "rules", "tests", "assets",
    "resources", "examples", "node_modules", "worktrees",
}


def _split_frontmatter_and_body(content: str) -> Tuple[str, str]:
    """Split markdown into frontmatter text and remaining body."""
    lines = content.splitlines(keepends=True)
    if not lines or not lines[0].strip() == "---":
        return "", content

    fm_lines = []
    body_lines = []
    in_fm = True
    for line in lines[1:]:
        if in_fm:
            if line.strip() == "---":
                in_fm = False
            else:
                fm_lines.append(line)
        else:
            body_lines.append(line)
    return "".join(fm_lines), "".join(body_lines)


def parse_frontmatter_depends_on(content: str) -> List[str]:
    """Parse depends-on entries from YAML frontmatter."""
    fm_text, _ = _split_frontmatter_and_body(content)
    if not fm_text:
        # Check if entire content is just frontmatter
        fm_text = content

    deps: List[str] = []

    # 1. Bracket syntax: depends-on: [a, b, c]
    bracket_match = re.search(r"^depends-on:\s*\[([^\]]*)\]", fm_text, re.MULTILINE)
    if bracket_match:
        items = bracket_match.group(1).split(",")
        for item in items:
            cleaned = item.strip().strip("'\"")
            if cleaned:
                deps.append(cleaned)
        return deps

    # 2. YAML list syntax:
    # depends-on:
    #   - a
    #   - b
    list_match = re.search(r"^depends-on:\s*$(.*?)(?=^[a-zA-Z0-9_-]+:|\Z)", fm_text, re.MULTILINE | re.DOTALL)
    if list_match:
        block = list_match.group(1)
        for line in block.splitlines():
            item_match = re.match(r"^\s*-\s*([a-zA-Z0-9_-]+)", line)
            if item_match:
                deps.append(item_match.group(1).strip())

    return deps


def parse_body_skill_invocations(body: str) -> List[str]:
    """Parse Skill("<name>", ...) invocations from markdown body."""
    # Match Skill("slug", ...) or Skill('slug', ...)
    pattern = r'Skill\(["\']([a-zA-Z0-9_-]+)["\']'
    matches = re.findall(pattern, body)
    seen: Set[str] = set()
    result: List[str] = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def parse_slash_commands(text: str) -> List[str]:
    """Parse /<command> references while ignoring filesystem paths and URLs."""
    # Match slash command tokens preceded by whitespace, backtick, or line start
    pattern = r'(?:^|[\s`(\[])/([a-z][a-z0-9_-]+)'
    matches = re.findall(pattern, text)
    seen: Set[str] = set()
    result: List[str] = []
    for m in matches:
        if m in PATH_EXCLUSIONS:
            continue
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def _find_skills(base_dir: str) -> List[Tuple[str, str, str]]:
    """Discover all (skill_id, skill_path, plugin_name) under base_dir."""
    skills: List[Tuple[str, str, str]] = []

    # Case 1: Direct skills directory (skills/<slug>/SKILL.md)
    if os.path.basename(base_dir.rstrip("/")) == "skills":
        skills_root = base_dir
    else:
        candidate = os.path.join(base_dir, "skills")
        skills_root = candidate if os.path.isdir(candidate) else base_dir

    if os.path.isdir(skills_root):
        for entry in os.listdir(skills_root):
            entry_path = os.path.join(skills_root, entry)
            if os.path.isdir(entry_path):
                skill_md = os.path.join(entry_path, "SKILL.md")
                if os.path.isfile(skill_md):
                    skills.append((entry, skill_md, "standalone"))

    # Case 2: Plugins directory (plugins/<plugin>/skills/<slug>/SKILL.md)
    plugins_root = os.path.join(base_dir, "plugins")
    if os.path.isdir(plugins_root):
        for plugin in os.listdir(plugins_root):
            p_skills_dir = os.path.join(plugins_root, plugin, "skills")
            if os.path.isdir(p_skills_dir):
                for entry in os.listdir(p_skills_dir):
                    entry_path = os.path.join(p_skills_dir, entry)
                    if os.path.isdir(entry_path):
                        skill_md = os.path.join(entry_path, "SKILL.md")
                        if os.path.isfile(skill_md):
                            skills.append((entry, skill_md, plugin))

    return skills


def extract_skill_graph(skills_dir: str, include_internal_pairs: bool = True) -> Dict[str, Any]:
    """Extract canonical Labeled Property Graph JSON from skills directory."""
    discovered = _find_skills(skills_dir)
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    known_skill_ids: Set[str] = {s[0] for s in discovered}

    for skill_id, skill_path, plugin in discovered:
        nodes.append({
            "id": skill_id,
            "type": "skill",
            "plugin": plugin,
            "path": skill_path,
        })

        try:
            with open(skill_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            sys.stderr.write(f"WARN: Failed to read {skill_path}: {e}\n")
            continue

        fm_text, body = _split_frontmatter_and_body(content)

        # 1. Frontmatter DEPENDS_ON
        deps = parse_frontmatter_depends_on(content)
        for dep in deps:
            edges.append({
                "source": skill_id,
                "target": dep,
                "kind": "DEPENDS_ON",
                "weight": 3.0,
            })

        # 2. Body INVOKES_SKILL
        invocations = parse_body_skill_invocations(body)
        for target in invocations:
            edges.append({
                "source": skill_id,
                "target": target,
                "kind": "INVOKES_SKILL",
                "weight": 2.0,
            })

        # 3. Body INVOKES_SLASH
        slash_cmds = parse_slash_commands(body)
        for cmd in slash_cmds:
            # Avoid self-referencing and duplicate edges
            if cmd != skill_id:
                edges.append({
                    "source": skill_id,
                    "target": cmd,
                    "kind": "INVOKES_SLASH",
                    "weight": 1.0,
                })

    # 4. PAIR_OF_INTERNAL mappings
    if include_internal_pairs:
        for priv, pub in PAIR_OF_INTERNAL_MAPPINGS.items():
            # If at least one node is in known set or target directory
            if priv in known_skill_ids or pub in known_skill_ids:
                edges.append({
                    "source": priv,
                    "target": pub,
                    "kind": "PAIR_OF_INTERNAL",
                    "weight": 4.0,
                })

    return {
        "nodes": nodes,
        "edges": edges,
    }


def main() -> None:
    """CLI Entrypoint."""
    parser = argparse.ArgumentParser(description="Skill Topology Graph Extractor")
    parser.add_argument("--skills-dir", default="skills", help="Directory containing skills or repository root")
    parser.add_argument("--output", "-o", help="Path to write output graph JSON")
    parser.add_argument("--format", choices=["json", "mermaid"], default="json", help="Output format")
    args = parser.parse_args()

    skills_dir = os.path.abspath(args.skills_dir)
    if not os.path.isdir(skills_dir):
        sys.stderr.write(f"ERROR: skills directory not found: {skills_dir}\n")
        sys.exit(1)

    graph = extract_skill_graph(skills_dir)

    if args.format == "json":
        formatted = json.dumps(graph, indent=2, ensure_ascii=False)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(formatted)
        else:
            print(formatted)
    elif args.format == "mermaid":
        lines = ["graph TD"]
        for edge in graph["edges"]:
            lines.append(f'    {edge["source"]} -->|{edge["kind"]}| {edge["target"]}')
        result = "\n".join(lines)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
        else:
            print(result)


if __name__ == "__main__":
    main()
