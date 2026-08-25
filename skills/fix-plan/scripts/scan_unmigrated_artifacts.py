#!/usr/bin/env python3
"""
scan_unmigrated_artifacts.py

Scans volatile brain session directories (~/.gemini/antigravity-ide/brain/*)
and checks whether artifacts (plan-*.md, research-*.md, walkthrough-*.md, implementation_plan.md)
are properly migrated to canonical workspace directories:
- ./.agents/docs/generated/ (default)
- ./llm-wiki/outputs/
- ./llm-wiki/pages/

Usage:
  python3 scan_unmigrated_artifacts.py [--migrate] [--dry-run] [--target-dir <dir>]
"""

import os
import sys
import re
import shutil
import argparse
from datetime import datetime
from pathlib import Path

def get_default_brain_roots(user_home=None):
    """
    Returns default brain roots for both Antigravity IDE and CLI runtimes.
    """
    home = Path(user_home) if user_home else Path(os.path.expanduser("~"))
    roots = [
        home / ".gemini" / "antigravity-ide" / "brain",
        home / ".gemini" / "antigravity-cli" / "brain"
    ]
    return roots

DEFAULT_BRAIN_ROOT = Path(os.path.expanduser("~/.gemini/antigravity-ide/brain"))

def get_default_canonical_search_dirs():
    """
    Returns generic workspace-relative canonical directories
    and any extra search directories specified via environment variable.
    """
    dirs = [
        Path.cwd() / ".agents" / "docs" / "generated",
        Path.cwd() / "llm-wiki" / "outputs",
        Path.cwd() / "llm-wiki" / "pages",
        Path.cwd() / "docs" / "generated",
    ]
    env_dirs = os.environ.get("ANTIGRAVITY_CANONICAL_SEARCH_DIRS")
    if env_dirs:
        separator = ";" if os.name == "nt" else ":"
        for p in env_dirs.split(separator):
            if p.strip():
                dirs.append(Path(os.path.expanduser(p.strip())))
    return dirs

def collect_canonical_files(search_dirs=None):
    if search_dirs is None:
        search_dirs = get_default_canonical_search_dirs()
    canonical_map = {}
    for cdir in search_dirs:
        if not cdir.exists():
            continue
        for root, _, files in os.walk(cdir):
            for f in files:
                if f.endswith(".md"):
                    canonical_map[f] = Path(root) / f
    return canonical_map

def scan_brain_artifacts_multi(brain_roots=None, search_dirs=None):
    if brain_roots is None:
        brain_roots = get_default_brain_roots()

    canonical_map = collect_canonical_files(search_dirs=search_dirs)
    artifacts = []
    seen_keys = set()

    for brain_root in brain_roots:
        if not brain_root.exists():
            continue

        for session_dir in brain_root.iterdir():
            if not session_dir.is_dir():
                continue
            session_id = session_dir.name

            for root, dirs, files in os.walk(session_dir):
                if ".system_generated" in root or "scratch" in root:
                    continue
                for f in files:
                    if not f.endswith(".md"):
                        continue
                    if not (f.startswith("plan-") or f.startswith("research-") or f.startswith("walkthrough-") or f.startswith("roadmap-")):
                        continue

                    full_path = Path(root) / f
                    key = (session_id, f)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    size = full_path.stat().st_size
                    mtime = full_path.stat().st_mtime
                    mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

                    try:
                        content = full_path.read_text(encoding="utf-8")
                        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                        title = title_match.group(1).strip() if title_match else f
                    except Exception:
                        title = f

                    is_migrated = f in canonical_map

                    artifacts.append({
                        "filename": f,
                        "session_id": session_id,
                        "brain_path": full_path,
                        "title": title,
                        "size": size,
                        "mtime": mtime,
                        "mtime_str": mtime_str,
                        "is_migrated": is_migrated,
                        "canonical_path": canonical_map.get(f)
                    })

    return sorted(artifacts, key=lambda x: x["mtime"], reverse=True)

def scan_brain_artifacts(brain_root=DEFAULT_BRAIN_ROOT, search_dirs=None):
    return scan_brain_artifacts_multi(brain_roots=[brain_root], search_dirs=search_dirs)

def migrate_artifacts(artifacts, target_dir, dry_run=False):
    target_path = Path(target_dir)
    if not dry_run:
        target_path.mkdir(parents=True, exist_ok=True)

    migrated = []
    for a in artifacts:
        dest = target_path / a["filename"]
        if not dry_run:
            shutil.copy2(a["brain_path"], dest)
        migrated.append({
            "filename": a["filename"],
            "source": a["brain_path"],
            "dest": dest
        })
    return migrated

def main():
    parser = argparse.ArgumentParser(description="Scan and migrate unmigrated brain artifacts")
    parser.add_argument("--migrate", action="store_true", help="Physically copy unmigrated artifacts to canonical destination")
    parser.add_argument("--target-dir", help="Destination canonical directory (default: current workspace ./.agents/docs/generated/)")
    parser.add_argument("--search-dirs", nargs="+", help="Canonical search directories to check for existing migrated artifacts")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without modifying files")
    args = parser.parse_args()

    search_dirs = [Path(os.path.expanduser(p)) for p in args.search_dirs] if args.search_dirs else None
    artifacts = scan_brain_artifacts_multi(search_dirs=search_dirs)
    unmigrated = [a for a in artifacts if not a["is_migrated"]]

    print(f"=== Brain Artifact Scan Summary ===")
    print(f"Total brain artifacts: {len(artifacts)}")
    print(f"Migrated artifacts:    {len(artifacts) - len(unmigrated)}")
    print(f"Unmigrated artifacts:  {len(unmigrated)}")
    print()

    if not unmigrated:
        print("All brain artifacts are cleanly migrated to canonical directories!")
        return

    print("--- Unmigrated Artifacts Found ---")
    for i, a in enumerate(unmigrated, 1):
        print(f"{i}. [{a['mtime_str']}] {a['filename']} ({a['size']} bytes)")
        print(f"   Title:   {a['title']}")
        print(f"   Session: {a['session_id']}")
        print(f"   Source:  {a['brain_path']}")
        print()

    if args.migrate:
        default_target = Path.cwd() / ".agents" / "docs" / "generated"
        target_dir = Path(args.target_dir) if args.target_dir else default_target
        print(f"--- Migrating {len(unmigrated)} Artifacts to {target_dir} ---")
        migrated = migrate_artifacts(unmigrated, target_dir=target_dir, dry_run=args.dry_run)
        for m in migrated:
            print(f"-> Copied {m['filename']} to {m['dest']}")
        print("Migration complete!")

if __name__ == "__main__":
    main()
