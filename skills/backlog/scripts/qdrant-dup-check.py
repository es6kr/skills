#!/usr/bin/env python3
"""qdrant-dup-check.py - warn-only semantic duplicate check for Plane registration.

Usage:
  uvx --from fastembed --with requests python qdrant-dup-check.py --text "<title>\\n<summary>" \\
      [--threshold 0.85] [--collection agent-memory-personal] [--qdrant-url http://...] [--limit 3]

Exit codes:
  0 - no duplicate signal, OR the check itself was skipped (fastembed missing,
      Qdrant unreachable/misconfigured) -- fail-open by design.
  3 - one or more semantic hits at/above --threshold were found; the top hits
      are printed to stdout for the caller to relay to the user (typically via
      AskUserQuestion: proceed / reuse existing item / hold).

This is Phase 2 of the hybrid duplicate-detection gate for Plane issue
registration. Phase 1 (exact-title REST guard) already lives directly inside
plane_create_entity.py / plane_create_issue.py's create_via_rest_api(). This
script is a deliberately separate, WARNING-only layer -- it never blocks
registration itself and has no write side effects (Qdrant is queried
read-only); the caller decides what to do with exit code 3.

Design source: .agents/docs/generated/plan-duplicate-detection-architecture.md
  Section 1 (Phase 2 approach), Section 3 (code snippet this implements),
  Section 5 (blast radius: read-only, graceful skip on any failure).

Wiring this into plane_create_entity.py / plane_create_issue.py (the
interactive AskUserQuestion step on a hit) is deliberately left for a
follow-up change -- that step needs a human in the loop to decide proceed /
reuse / hold, which an autonomous Ralph loop cannot exercise or verify.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_NAME = "fast-paraphrase-multilingual-minilm-l12-v2"
DEFAULT_COLLECTION = os.environ.get("COLLECTION_NAME") or "agent-memory-personal"
DEFAULT_QDRANT_URL = os.environ.get("QDRANT_URL") or "http://192.168.6.176:30333"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Warn-only semantic duplicate check before registering a Plane issue/artifact"
    )
    parser.add_argument("--text", required=True, help="Title (+ optional summary) of the item about to be registered")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Similarity score at/above which a hit is reported (default: 0.85, unvalidated hypothesis -- see plan #7(a))",
    )
    parser.add_argument("--collection", default=DEFAULT_COLLECTION, help=f"Qdrant collection to search (default: {DEFAULT_COLLECTION})")
    parser.add_argument("--qdrant-url", default=DEFAULT_QDRANT_URL, help=f"Qdrant base URL (default: {DEFAULT_QDRANT_URL})")
    parser.add_argument("--limit", type=int, default=3, help="Max number of hits to print (default: 3)")
    return parser.parse_args(argv)


def qdrant_auth_headers():
    """Read-only API key header, if configured. See qdrant-search.py for the same convention."""
    key = os.environ.get("QDRANT_READ_ONLY_API_KEY") or os.environ.get("QDRANT_API_KEY")
    return {"api-key": key} if key else {}


def embed(text):
    """fastembed required. Deferred import so argparse --help works without it installed."""
    from fastembed import TextEmbedding

    model = TextEmbedding(MODEL)
    return list(model.embed([text]))[0].tolist()


def search(qdrant_url, collection, vector, limit):
    req = urllib.request.Request(
        f"{qdrant_url}/collections/{collection}/points/search",
        data=json.dumps(
            {"vector": {"name": VECTOR_NAME, "vector": vector}, "limit": limit, "with_payload": True}
        ).encode(),
        headers={"Content-Type": "application/json", **qdrant_auth_headers()},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["result"]


def render_hit(hit):
    payload = hit.get("payload") or {}
    doc = str(payload.get("document") or "")
    snippet = doc[:120].replace("\n", " ")
    meta = payload.get("metadata") or {}
    url = meta.get("issue_url") or meta.get("pr_url") or ""
    suffix = f" ({url})" if url else ""
    return f"  score={hit.get('score'):.3f}  {snippet}{suffix}"


def skip(reason):
    print(f"SKIP (qdrant-dup-check): {reason} -- registration proceeds unchecked.", file=sys.stderr)
    sys.exit(0)


def main(argv=None):
    args = parse_args(argv)

    try:
        vector = embed(args.text)
    except ImportError:
        skip("fastembed not installed")
    except Exception as exc:  # noqa: BLE001 -- any embedding failure must fail open
        skip(f"embedding failed ({exc})")

    try:
        hits = search(args.qdrant_url, args.collection, vector, args.limit)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        skip(f"Qdrant unreachable ({exc})")
    except Exception as exc:  # noqa: BLE001 -- any search failure must fail open
        skip(f"search failed ({exc})")

    top_hits = [h for h in hits if h.get("score", 0) >= args.threshold]
    if not top_hits:
        sys.exit(0)

    print(f"DUP-SIGNAL (qdrant-dup-check): {len(top_hits)} hit(s) >= threshold {args.threshold}:")
    for hit in top_hits[: args.limit]:
        print(render_hit(hit))
    sys.exit(3)


if __name__ == "__main__":
    main()
