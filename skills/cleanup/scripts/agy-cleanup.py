#!/usr/bin/env python3
"""
Antigravity Session Cleanup Runner (agy-cleanup.py)
Sequentially inspects and verifies the 5-step cleanup pipeline in Antigravity (Gemini) environments.
Provides empirical evidence (context tokens, git status, FA records, RAG availability, rename suggestions).
"""

import os
import sys
import subprocess
import urllib.request
import re
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run_cmd(cmd, cwd=None):
    try:
        res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=10)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def check_context_usage():
    print("=== [Step 0.1] Context Usage Measurement ===")
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
            print(out)
            return out
    print("Context usage: Unknown (context-usage-now.sh not found or error)")
    return "Unknown"


def check_git_status():
    print("\n=== [Step 1] Git Status Check ===")
    code, out, _ = run_cmd("git status --short")
    if code == 0:
        if not out:
            print("Working tree clean (no uncommitted changes).")
        else:
            lines = out.splitlines()
            print(f"Uncommitted/staged changes ({len(lines)} files):")
            for line in lines[:10]:
                print(f"  {line}")
            if len(lines) > 10:
                print(f"  ... and {len(lines) - 10} more files")
    else:
        print("Git status check failed or not inside a git repository.")


def check_fa_records():
    print("\n=== [Step 2] Self-Improve / FA Records Check ===")
    fa_store = os.environ.get("FA_DATA_DIR")
    if not fa_store:
        fa_store = Path.home() / ".claude/skills/cleanup/data"
    else:
        fa_store = Path(fa_store)

    fa_file = fa_store / "failed-attempts.md"
    if fa_file.exists():
        try:
            with open(fa_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()][:15]
            print(f"Latest FA records ({fa_file}):")
            for l in lines[:5]:
                print(f"  {l}")
        except Exception as e:
            print(f"Failed to read FA store: {e}")
    else:
        print(f"FA store file not found: {fa_file}")


def check_rag_readyz():
    print("\n=== [Step 3] Knowledge / RAG Receiver Status ===")
    url = "http://localhost:30333/readyz"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                print(f"Local Qdrant RAG ready: {url} -> 200 OK")
                return True
            else:
                print(f"Local Qdrant RAG returned status: {resp.status}")
                return False
    except Exception:
        print(f"Local Qdrant RAG receiver unreachable ({url}). RAG store deferred (0 chunks).")
        return False


def check_checklists():
    print("\n=== [Step 4] Checklist / Backlog Status ===")
    for p in [Path(".agents/fix_plan.md"), Path("fix_plan.md"), Path("task.md")]:
        if p.exists():
            print(f"Found active tracker: {p}")


def generate_rename_suggestions(sess_id=None, slug="task"):
    print("\n=== [Step 5] Session Rename Suggestions (/rename) ===")
    sess8 = (sess_id or "00000000")[:8]
    slug = re.sub(r"[^a-zA-Z0-9\-]", "-", slug).strip("-")[:16]
    suggestions = [
        f"/rename agy-{slug}-{sess8}",
        f"/rename flash-{slug}-{sess8}"
    ]
    for s in suggestions:
        if len(s) <= 38: # "/rename " (8) + 30 chars
            print(f"  {s}")


def main():
    sess_id = sys.argv[1] if len(sys.argv) > 1 else None
    slug = sys.argv[2] if len(sys.argv) > 2 else "cleanup"

    print("==================================================")
    print(" Antigravity Physical Cleanup Inspection Pipeline")
    print("==================================================")
    check_context_usage()
    check_git_status()
    check_fa_records()
    check_rag_readyz()
    check_checklists()
    generate_rename_suggestions(sess_id, slug)
    print("\n==================================================")
    print(" Cleanup pipeline inspection completed.")
    print("==================================================")


if __name__ == "__main__":
    main()
