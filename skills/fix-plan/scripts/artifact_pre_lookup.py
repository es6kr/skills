#!/usr/bin/env python3
"""
artifact_pre_lookup.py - Pre-Creation Lookup Module for Plan & Research Artifacts
Queries workspace-isolated Qdrant collections and LLM Wiki files to generate a
'## Prior Knowledge & Context' header before creating new plan/research documents.
Uses standard library (urllib) for zero external dependencies.
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import argparse
from pathlib import Path
from workspace_profile import get_profile


def query_qdrant_context(profile: dict, query_text: str, top_k: int = 3) -> list:
    """Query Qdrant collections for relevant past context."""
    results = []
    qdrant_url = profile["qdrant_url"]
    collections = [profile["qdrant_wiki_collection"], profile["qdrant_memory_collection"]]

    for col in collections:
        try:
            url = f"{qdrant_url}/collections/{col}/points/scroll"
            req_data = json.dumps({"limit": top_k, "with_payload": True, "with_vector": False}).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"}, method="POST")

            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    points = data.get("result", {}).get("points", [])
                    for p in points:
                        pl = p.get("payload", {})
                        doc = pl.get("text") or pl.get("document") or ""
                        if doc and any(kw.lower() in doc.lower() for kw in query_text.split() if len(kw) > 2):
                            results.append({
                                "collection": col,
                                "title": pl.get("title") or pl.get("section_h2") or pl.get("topic") or "Knowledge Chunk",
                                "snippet": doc[:200].replace("\n", " ").strip()
                            })
        except Exception:
            pass

    return results[:top_k]


def query_llm_wiki(profile: dict, query_text: str) -> list:
    """Search local LLM Wiki pages for relevant cross-references."""
    wiki_path = Path(profile["llm_wiki_path"]) / "pages"
    results = []
    if not wiki_path.exists():
        return results

    query_terms = [q.lower() for q in query_text.split() if len(q) > 2]
    for md_file in wiki_path.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            if any(term in content.lower() for term in query_terms):
                title = md_file.stem
                for line in content.splitlines():
                    if line.startswith("title:"):
                        title = line.replace("title:", "").strip()
                        break
                results.append({
                    "file": md_file.name,
                    "title": title,
                    "snippet": content[:180].replace("\n", " ").strip()
                })
        except Exception:
            pass

    return results[:3]


def generate_prior_context_header(query_text: str, workspace: str = None) -> str:
    """Generate Markdown '## Prior Knowledge & Context' block."""
    profile = get_profile(workspace_name=workspace)

    qdrant_hits = query_qdrant_context(profile, query_text)
    wiki_hits = query_llm_wiki(profile, query_text)

    output = []
    output.append(f"## Prior Knowledge & Context (Workspace: {profile['workspace_name']})")
    output.append("")

    if not qdrant_hits and not wiki_hits:
        output.append("> *No directly matching prior knowledge found in Qdrant or LLM Wiki for this topic.*")
        output.append("")
        return "\n".join(output)

    if wiki_hits:
        output.append("### Relevant LLM Wiki Pages")
        for hit in wiki_hits:
            output.append(f"- **[[{hit['file'].replace('.md', '')}]]** ({hit['title']}): {hit['snippet']}...")
        output.append("")

    if qdrant_hits:
        output.append("### Related Vector Memory Hits (Qdrant)")
        for hit in qdrant_hits:
            output.append(f"- **[{hit['collection']}] {hit['title']}**: {hit['snippet']}...")
        output.append("")

    return "\n".join(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-Creation Knowledge Lookup")
    parser.add_argument("query", help="Topic or title of the plan/research artifact")
    parser.add_argument("--workspace", help="Workspace profile override (must exist in config.json profiles)")
    args = parser.parse_args()

    header = generate_prior_context_header(args.query, workspace=args.workspace)
    print(header)
