#!/usr/bin/env python3
"""RAG batch store for fa-prune COLD demotes (fa-classify.py --cut output consumer).

Reads a --cut directory (index.json + NNN.md section bodies) produced by
fa-classify.py and upserts one chunk per section into the RAG backend using
the fa-prune.md Section 8 receiver protocol:

  payload = {document, metadata: {type, project, date, category,
                                  source_file, section_title, chunk_key}}
  id      = uuid5(NAMESPACE_URL, "fa-archive:<source_file>:<title>")  (idempotent)

Embedding matches the MCP receiver exactly (same model, same named vector),
so chunks stored here are indistinguishable from MCP-stored ones. Use this
as the HTTP fallback when the receiver MCP is down (e.g., container runtime
outage) or for --backfill of pre-existing archive files.

Usage:
  uv run --with fastembed --with requests python fa-batch-store.py \
      --cut-dir /tmp/fa-cold --source-file failed-attempts-archive-<date>.md
  # backfill mode: store raw archive .md files directly (no --cut step)
  uv run --with fastembed --with requests python fa-batch-store.py \
      --backfill <archive1.md> [<archive2.md> ...] [--skip-existing]

Prints the mandatory quantity report line (skill-usage.md "RAG store report format"):
  RAG store summary: N chunks added (receiver: <collection>@<url>)
"""
import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path

# Instance-specific values come from the environment — no personal endpoint
# ships in published source. Override via --url / env as needed.
DEFAULT_URL = os.environ.get("RAG_URL", "http://localhost:6333")
DEFAULT_COLLECTION = os.environ.get("RAG_COLLECTION", "claude-memory")
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_CACHE = str(Path.home() / ".cache/fastembed-qdrant-mcp")
VECTOR_NAME = os.environ.get("RAG_VECTOR_NAME", "fast-paraphrase-multilingual-minilm-l12-v2")
DOC_PREFIX = "[archived-failure-pattern] "
DOC_MAX = 2800  # embed window; payload keeps the same truncated document
DATE = re.compile(r"\((\d{4}-\d{2}-\d{2})")


def make_point(model, body, title, source_file, date):
    doc = f"{DOC_PREFIX}{body[:DOC_MAX]}"
    vec = list(model.embed([doc]))[0].tolist()
    key = f"fa-archive:{source_file}:{title}"
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, key)),
        "vector": {VECTOR_NAME: vec},
        "payload": {"document": doc, "metadata": {
            "type": "archived-failure-pattern", "project": "cleanup-skill",
            "date": date, "category": "fa-prune-archive",
            "source_file": source_file, "section_title": title,
            "chunk_key": key,
        }},
    }


def sections_of(text):
    for s in re.split(r"(?m)^## ", text)[1:]:
        body = "## " + s
        title = body.split("\n", 1)[0][3:].strip()
        dates = DATE.findall(body)
        yield title, body, (max(dates) if dates else "")


def existing_titles(base, collection, source_files):
    import requests
    seen = set()
    r = requests.post(f"{base}/collections/{collection}/points/scroll", json={
        "filter": {"must": [{"key": "metadata.category",
                             "match": {"value": "fa-prune-archive"}}]},
        "limit": 1000, "with_payload": ["metadata"], "with_vector": False,
    }, timeout=20)
    for p in r.json()["result"]["points"]:
        m = p["payload"].get("metadata") or {}
        if not source_files or m.get("source_file") in source_files:
            seen.add((m.get("source_file"), m.get("section_title")))
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut-dir", help="fa-classify.py --cut output dir (index.json)")
    ap.add_argument("--source-file", help="archive filename recorded in metadata "
                                          "(required with --cut-dir)")
    ap.add_argument("--backfill", nargs="+", help="raw archive .md files to store")
    ap.add_argument("--skip-existing", action="store_true",
                    help="scroll receiver first; skip (source_file, title) pairs already stored")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--collection", default=DEFAULT_COLLECTION)
    args = ap.parse_args()
    if not args.cut_dir and not args.backfill:
        ap.error("one of --cut-dir or --backfill is required")
    if args.cut_dir and not args.source_file:
        ap.error("--source-file is required with --cut-dir")

    import requests
    from fastembed import TextEmbedding
    model = TextEmbedding(DEFAULT_MODEL, cache_dir=DEFAULT_CACHE)

    jobs = []  # (title, body, date, source_file)
    if args.cut_dir:
        cut = Path(args.cut_dir)
        for e in json.loads((cut / "index.json").read_text(encoding="utf-8")):
            body = (cut / e["file"]).read_text(encoding="utf-8")
            jobs.append((e["title"], body, e.get("date", ""), args.source_file))
    for f in args.backfill or []:
        fp = Path(f)
        for title, body, date in sections_of(fp.read_text(encoding="utf-8")):
            jobs.append((title, body, date, fp.name))

    if args.skip_existing:
        seen = existing_titles(args.url, args.collection,
                               {j[3] for j in jobs})
        jobs = [j for j in jobs if (j[3], j[0]) not in seen]

    points = [make_point(model, b, t, sf, d) for t, b, d, sf in jobs]
    if points:
        r = requests.put(
            f"{args.url}/collections/{args.collection}/points?wait=true",
            json={"points": points}, timeout=120)
        r.raise_for_status()
    print(f"RAG store summary: {len(points)} chunks added "
          f"(receiver: {args.collection}@{args.url})")
    for t, _, _, sf in jobs:
        print(f"  - [{sf}] {t[:80]}")


if __name__ == "__main__":
    main()
