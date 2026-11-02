#!/usr/bin/env python3
"""
Antigravity Session Cleanup Runner (agy-cleanup.py)
Graph-driven execution runtime:
  All procedures, stages, dependencies, and guards are defined AUTHORITATIVELY in
  Dgraph (tenant 'es6kr:cleanup', prefix 'rag_graph_v1') and indexed in Qdrant.
  This script does NOT define procedures; it retrieves and verifies the workflow from
  cleanup_query.py (SSOT), and executes the physical adapters mapped to each graph stage.

Usage:
  python3 agy-cleanup.py [session_id] [slug] [--execute]
"""

import os
import sys
import subprocess
import urllib.request
import urllib.parse
import ssl
import ipaddress
import re
import json
import time
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run_cmd(cmd, cwd=None, timeout=30):
    try:
        res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def load_env_keys():
    """Load Qdrant and RAG environment variables from ~/.rag-store-keys.env if present."""
    env_file = Path.home() / ".rag-store-keys.env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and not os.environ.get(k):
                            os.environ[k] = v
        except Exception:
            pass


def resolve_rag_endpoint():
    """Resolve active Qdrant RAG endpoint from env, ws-config (~/.agents/config.json), or default."""
    load_env_keys()
    if os.environ.get("WSCFG_RAG_ENDPOINT"):
        return os.environ["WSCFG_RAG_ENDPOINT"].rstrip("/")
    if os.environ.get("QDRANT_URL"):
        return os.environ["QDRANT_URL"].rstrip("/")

    config_path = Path.home() / ".agents/config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                endpoint = data.get("global", {}).get("rag", {}).get("endpoint")
                if endpoint:
                    return endpoint.rstrip("/")
        except Exception:
            pass

    return "https://192.168.6.176:30333"


def ssl_context_for_url(url: str):
    """Return an SSL context with certificate verification disabled for private IP targets."""
    ctx = ssl.create_default_context()
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
        except ValueError:
            pass
    except Exception:
        pass
    return ctx


def load_procedure_graph(topic: str = "run") -> dict:
    """Retrieve and verify the authoritative cleanup procedure subgraph from Dgraph & Qdrant."""
    query_script = Path.home() / ".agents/plugins/rag/skills/graph-ledger/scripts/cleanup_query.py"
    if not query_script.exists():
        raise RuntimeError(f"Authoritative procedure query script not found: {query_script}")

    cmd = f'python3 "{query_script}" load --topic {topic}'
    code, out, err = run_cmd(cmd)
    if code != 0:
        raise RuntimeError(f"Dgraph procedure query failed (code {code}): {err or out}")

    try:
        data = json.loads(out)
    except Exception as e:
        raise RuntimeError(f"Failed to parse procedure graph JSON: {e}")

    val = data.get("validation", {})
    if not val.get("verified"):
        raise RuntimeError(f"Procedure graph validation failed: {val}")

    return data


def check_context_usage():
    bash_bin = r"C:\Program Files\Git\bin\bash.exe" if os.path.exists(r"C:\Program Files\Git\bin\bash.exe") else "bash"
    script_candidates = [
        Path.home() / "ghq/github.com/es6kr/skills/skills/session/resources/context-usage-now.sh",
        Path.home() / ".agents/skills/session/resources/context-usage-now.sh",
        Path.home() / ".claude/skills/session/resources/context-usage-now.sh"
    ]
    script_path = None
    for cand in script_candidates:
        if cand.exists():
            script_path = cand
            break

    if script_path:
        code, out, _ = run_cmd(f'"{bash_bin}" "{script_path}"')
        if code == 0 and out:
            print(f"  {out}")
            return out
    print("  Context usage: Unknown (context-usage-now.sh not found or error)")
    return "Unknown"


def check_git_status(verbose=True):
    candidates = [
        Path.cwd(),
        Path.cwd() / "claude-plugins",
        Path.home() / ".agents",
        Path.cwd() / "skills"
    ]

    checked_paths = set()
    results = {}

    for cand in candidates:
        resolved = cand.resolve()
        if resolved in checked_paths or not resolved.exists():
            continue
        checked_paths.add(resolved)

        code, is_inside, _ = run_cmd("git rev-parse --is-inside-work-tree", cwd=resolved)
        if code != 0 or is_inside != "true":
            continue

        code, out, _ = run_cmd("git status --short", cwd=resolved)
        if code == 0:
            lines = [l for l in out.splitlines() if l.strip()]
            results[str(resolved)] = lines
            if verbose:
                rel_name = resolved.name or str(resolved)
                if not lines:
                    print(f"  [{rel_name}] Clean (no uncommitted changes)")
                else:
                    print(f"  [{rel_name}] {len(lines)} uncommitted file(s):")
                    for line in lines[:5]:
                        print(f"    {line}")
                    if len(lines) > 5:
                        print(f"    ... and {len(lines) - 5} more files")

    return results


def check_fa_records():
    fa_store = os.environ.get("FA_DATA_DIR")
    candidates = []
    if fa_store:
        candidates.append(Path(fa_store) / "failed-attempts.md")
    candidates.extend([
        Path.home() / ".agents/skills/cleanup/data/failed-attempts.md",
        Path.home() / ".claude/skills/cleanup/data/failed-attempts.md",
    ])
    fa_file = None
    for cand in candidates:
        if cand.exists():
            fa_file = cand
            break

    if fa_file and fa_file.exists():
        try:
            with open(fa_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()][:15]
            print(f"  FA store ({fa_file.name}):")
            for l in lines[:5]:
                print(f"    {l}")
        except Exception as e:
            print(f"  Failed to read FA store: {e}")
    else:
        print(f"  FA store file not found in candidates")


def check_rag_readyz(sess_id=None):
    endpoint = resolve_rag_endpoint()
    url = f"{endpoint}/healthz"
    is_ready = False

    headers = {}
    api_key = os.environ.get("QDRANT_API_KEY") or os.environ.get("QDRANT_READ_ONLY_API_KEY")
    if api_key:
        headers["api-key"] = api_key

    try:
        req = urllib.request.Request(url, method="GET", headers=headers)
        ctx = ssl_context_for_url(url)
        with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
            if resp.status == 200:
                print(f"  Qdrant RAG receiver ready: {url} -> 200 OK")
                is_ready = True
            else:
                print(f"  Qdrant RAG returned status: {resp.status}")
    except Exception as e:
        print(f"  Qdrant RAG receiver unreachable ({url}): {e}")

    turn_count = 0
    if sess_id:
        candidates = [
            Path.home() / f".gemini/antigravity-cli/brain/{sess_id}/.system_generated/logs/transcript.jsonl",
            Path.home() / f".gemini/antigravity-ide/brain/{sess_id}/.system_generated/logs/transcript.jsonl"
        ]
        transcript_path = None
        for c in candidates:
            if c.exists():
                transcript_path = c
                break

        if transcript_path:
            try:
                with open(transcript_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        if entry.get("type") == "USER_INPUT":
                            turn_count += 1
                print(f"  Transcript: {transcript_path.name} -> {turn_count} user turn(s) / chunks detected.")
                print(f"  Format 3-C.1:\n    '{turn_count} chunks / {turn_count} turns added (session import, receiver: qdrant-import.py) — session UUID {sess_id}. M artifacts imported.'")
            except Exception as ex:
                print(f"  Failed to inspect transcript for session {sess_id}: {ex}")
        else:
            print(f"  Transcript JSONL for session {sess_id} not found in candidate paths.")

    return is_ready, turn_count


def detect_session_artifacts(sess_id=None):
    artifacts = []
    sess8 = (sess_id or "")[:8]
    doc_dirs = [
        Path(".agents/docs/generated"),
        Path(".agents/docs/shared"),
        Path.home() / ".agents/docs/generated",
        Path.home() / ".agents/docs/shared",
    ]

    seen = set()
    for d in doc_dirs:
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            if p.name in seen:
                continue
            is_match = False
            if sess8 and sess8 in p.name:
                is_match = True
            elif p.name.startswith("walkthrough-") or p.name.startswith("plan-"):
                try:
                    if (time.time() - p.stat().st_mtime) < 86400:
                        with open(p, "r", encoding="utf-8") as f:
                            head_text = f.read(2048)
                            if (sess8 and sess8 in head_text) or (sess_id and sess_id in head_text):
                                is_match = True
                except Exception:
                    pass

            if is_match:
                seen.add(p.name)
                art_type = "walkthrough" if "walkthrough" in p.name else "plan"
                collabmd_url = f"https://collabmd.dgs.ai.kr/#file=daegunsoftdev-agents-docs/{p.name}"
                artifacts.append({
                    "path": p,
                    "filename": p.name,
                    "type": art_type,
                    "collabmd_url": collabmd_url
                })

    return artifacts


def check_fixplan_qdrant_sync():
    fixplan_candidates = [
        Path(".agents/fix_plan.md"),
        Path("fix_plan.md"),
        Path.home() / "ghq/github.com/es6kr/.agents/fix_plan.md",
    ]
    target_fp = None
    for cand in fixplan_candidates:
        if cand.exists():
            target_fp = cand
            break

    script_path = Path.home() / ".agents/plugins/rag/skills/qdrant/scripts/fix-plan-to-qdrant.py"
    if not script_path.exists():
        script_path = Path.home() / ".claude/skills/qdrant/scripts/fix-plan-to-qdrant.py"

    if target_fp and script_path.exists():
        print(f"  Target fix_plan: {target_fp}")
        print(f"  Command 3-C.2:")
        print(f"    uvx --from fastembed --with requests python3 {script_path} --fix-plan {target_fp} --workspace es6kr")
    else:
        print(f"  fix_plan or fix-plan-to-qdrant.py not found")

    return target_fp, script_path


def check_checklists():
    for p in [Path(".agents/fix_plan.md"), Path("fix_plan.md"), Path("task.md")]:
        if p.exists():
            print(f"  Found active tracker: {p}")


def generate_rename_suggestions(sess_id=None, slug="cleanup", artifacts=None):
    sess8 = (sess_id or "00000000")[:8]
    slug = re.sub(r"[^a-zA-Z0-9\-]", "-", slug).strip("-")

    derived_slug = slug
    if derived_slug in ("task", "cleanup", "wip") and artifacts:
        for art in artifacts:
            clean_name = art["filename"].replace("walkthrough-", "").replace("plan-", "").replace(".md", "")
            clean_name = re.sub(r"-[a-f0-9]{8}$", "", clean_name)
            if clean_name:
                derived_slug = clean_name[:18].strip("-")
                break

    suggestions = []
    opt1 = f"/rename {derived_slug[:21]}-{sess8}"
    suggestions.append(opt1[:38])

    if derived_slug != slug:
        opt2 = f"/rename {slug[:21]}-{sess8}"
        suggestions.append(opt2[:38])
    else:
        opt2 = f"/rename agy-{derived_slug[:17]}-{sess8}"
        suggestions.append(opt2[:38])

    opt3 = f"/rename flash-{derived_slug[:15]}-{sess8}"
    suggestions.append(opt3[:38])

    return suggestions


def execute_pipeline(sess_id, target_fp, artifacts):
    print("\n--------------------------------------------------")
    print(" Physical Pipeline Execution (--execute)")
    print("--------------------------------------------------")
    endpoint = resolve_rag_endpoint()
    qdrant_import = Path.home() / ".agents/plugins/rag/skills/qdrant/scripts/qdrant-import.py"
    fix_plan_import = Path.home() / ".agents/plugins/rag/skills/qdrant/scripts/fix-plan-to-qdrant.py"

    if sess_id and qdrant_import.exists():
        print(f"\n[Execute 3-C.1] Importing session transcript ({sess_id})...")
        cmd = f'uvx --from fastembed --with requests python3 "{qdrant_import}" --session-id "{sess_id}" --collection agent-memory-personal --qdrant-url "{endpoint}"'
        code, out, err = run_cmd(cmd)
        if code == 0:
            print("  ✓ Session import completed successfully.")
        else:
            print(f"  ✗ Session import failed: {err or out}")

    if target_fp and fix_plan_import.exists():
        print(f"\n[Execute 3-C.2] Syncing fix_plan completed items ({target_fp})...")
        cmd = f'uvx --from fastembed --with requests python3 "{fix_plan_import}" --fix-plan "{target_fp}" --workspace es6kr --qdrant-url "{endpoint}"'
        code, out, err = run_cmd(cmd)
        if code == 0:
            print("  ✓ Fix-plan sync completed successfully.")
        else:
            print(f"  ✗ Fix-plan sync failed: {err or out}")

    if artifacts and qdrant_import.exists():
        for art in artifacts:
            if art["type"] == "walkthrough":
                print(f"\n[Execute 3-C.3] Indexing walkthrough artifact: {art['filename']}...")
                cmd = f'uvx --from fastembed --with requests python3 "{qdrant_import}" --source md --md-path "{art["path"]}" --collection agent-memory-personal --qdrant-url "{endpoint}"'
                code, out, err = run_cmd(cmd)
                if code == 0:
                    print("  ✓ Walkthrough artifact indexed successfully.")
                else:
                    print(f"  ✗ Walkthrough artifact indexing failed: {err or out}")


def query_cleanup_topology_references(topology_query_fn=None) -> dict:
    """Query Dgraph es6kr:topology for skill:cleanup dependencies and callers."""
    if topology_query_fn is not None:
        return topology_query_fn("skill:cleanup")

    try:
        rag_scripts = Path.home() / ".agents" / "plugins" / "rag" / "skills" / "graph-ledger" / "scripts"
        if str(rag_scripts) not in sys.path:
            sys.path.insert(0, str(rag_scripts))
        import agentify_topology
        return agentify_topology.run_query(skill_id="skill:cleanup", tenant="es6kr:topology")
    except Exception as e:
        return {"error": str(e), "dependencies": [], "callers": []}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    execute_mode = "--execute" in sys.argv or "--auto" in sys.argv

    sess_id = args[0] if len(args) > 0 else None
    slug = args[1] if len(args) > 1 else "cleanup"

    print("==================================================")
    print(" Antigravity Graph-Driven Cleanup Runner")
    print("==================================================")

    # 1. Authoritative Dgraph Procedure Retrieval & Verification (SSOT)
    print("\n[Dgraph SSOT Retrieval & Verification]")
    try:
        graph = load_procedure_graph(topic="run")
        val = graph.get("validation", {})
        print(f"  ✓ Subgraph Verified: {val.get('node_count')} nodes, {val.get('edge_count')} edges")
        print(f"  ✓ Graph Hash: {val.get('graph_hash')}")
        print(f"  ✓ Qdrant Index Point: {graph.get('index_point_id')}")
    except Exception as e:
        print(f"  ✗ HARD STOP: Dgraph procedure verification failed: {e}")
        sys.exit(1)

    # 1.5 Query Topology References for skill:cleanup
    topo_refs = query_cleanup_topology_references()
    if topo_refs.get("dependencies") or topo_refs.get("callers"):
        print("\n[Dgraph Topology References (tenant: es6kr:topology)]")
        deps = [d["target"].replace("skill:", "").replace("topic:cleanup:", "") for d in topo_refs.get("dependencies", [])]
        callers = [c["source"].replace("skill:", "") for c in topo_refs.get("callers", [])]
        print(f"  ✓ Skill: cleanup (registered in es6kr:topology)")
        print(f"  ✓ Outgoing Dependencies: {', '.join(deps[:10])}")
        print(f"  ✓ Incoming Callers: {', '.join(callers[:10])}")

    # 2. Iterate dynamically over stages defined by the DGraph graph
    stages = sorted(graph.get("stages", []), key=lambda s: s.get("properties", {}).get("order", 0))
    print(f"\n[Executing {len(stages)} Authoritative Graph Stages]")

    target_fp = None
    artifacts = []

    for stage in stages:
        order = stage.get("properties", {}).get("order", 0)
        label = stage.get("label", f"Stage {order}")
        print(f"\n=== [Graph Stage {order + 1}] {label} ===")

        if order == 0:  # 추적·보존 사전조건
            check_context_usage()
            check_rag_readyz(sess_id)

        elif order == 1:  # Git 마무리
            check_git_status()

        elif order == 2:  # Self-improve
            check_fa_records()

        elif order == 3:  # Knowledge Persist
            target_fp, _ = check_fixplan_qdrant_sync()
            artifacts = detect_session_artifacts(sess_id)
            if artifacts:
                print(f"  Detected Session Deliverables ({len(artifacts)} files):")
                for art in artifacts:
                    print(f"    - [{art['type'].upper()}] {art['filename']} ({art['collabmd_url']})")
            if execute_mode:
                execute_pipeline(sess_id, target_fp, artifacts)

        elif order == 4:  # Tracker / 보고
            check_checklists()

        elif order == 5:  # WIP 인계
            rename_suggestions = generate_rename_suggestions(sess_id, slug, artifacts)
            print("  Recommended standalone runnable code blocks (length <= 30 chars):")
            for s in rename_suggestions:
                print(f"  ```bash\n  {s}\n  ```")

    print("\n==================================================")
    print(" Graph-driven cleanup execution completed.")
    print("==================================================")


if __name__ == "__main__":
    main()
