#!/usr/bin/env python3
"""
workspace_profile.py - Multi-Workspace Profile Engine
Resolves target infrastructure endpoints, Qdrant collections, Plane hosts, and LLM Wiki paths
based on working directory context or explicit CLI flags.

Ships with zero hardcoded per-organization values. Real endpoints/paths live in
~/.config/plane-backlog/config.json under "profiles.<name>", keeping this script
reusable across environments. Example config.json:

{
  "profiles": {
    "myworkspace": {
      "workspace_name": "myworkspace",
      "plane_host": "https://plane.example.com",
      "plane_token_env": "MYWORKSPACE_PLANE_API_KEY",
      "qdrant_url": "http://localhost:6333",
      "qdrant_wiki_collection": "myworkspace-wiki",
      "qdrant_memory_collection": "claude-memory",
      "qdrant_task_collection": "fix-plan-myworkspace",
      "llm_wiki_path": "/path/to/llm-wiki",
      "default_project": "myworkspace",
      "cwd_match": ["myworkspace"]
    }
  }
}
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Config file location
CONFIG_FILE = Path.home() / ".config" / "plane-backlog" / "config.json"

DEFAULT_PROFILE = {
    "workspace_name": "default",
    "plane_host": "",
    "plane_token_env": "PLANE_API_KEY",
    "qdrant_url": "http://localhost:6333",
    "qdrant_wiki_collection": "wiki",
    "qdrant_memory_collection": "claude-memory",
    "qdrant_task_collection": "fix-plan",
    "llm_wiki_path": "",
    "default_project": "default"
}


def load_user_config():
    """Load user config from ~/.config/plane-backlog/config.json (holds all real per-workspace values)."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def detect_workspace(target_path: str = None) -> str:
    """Detect workspace profile based on env var, explicit path, or cwd match against configured profiles."""
    profiles = load_user_config().get("profiles", {})

    # 1. Environment variable override
    env_profile = os.environ.get("PLANE_WORKSPACE_PROFILE")
    if env_profile in profiles:
        return env_profile

    # 2. Check path against each configured profile's cwd_match tokens
    cwd = Path(target_path or os.getcwd()).resolve()
    cwd_str = str(cwd)

    for name, cfg in profiles.items():
        for token in cfg.get("cwd_match", [name]):
            if token in cwd_str:
                return name

    # 3. Default fallback — first configured profile, or "default" if none configured
    return next(iter(profiles), "default")


def get_profile(workspace_name: str = None, target_path: str = None) -> dict:
    """Get merged profile dictionary for given workspace."""
    user_config = load_user_config()
    profiles = user_config.get("profiles", {})
    name = workspace_name or detect_workspace(target_path)

    profile = DEFAULT_PROFILE.copy()
    profile.update(profiles.get(name, {}))
    profile.setdefault("workspace_name", name)

    # API Token resolution from ENV
    token_env = profile["plane_token_env"]
    profile["plane_token"] = os.environ.get(token_env) or os.environ.get("PLANE_API_KEY", "")

    return profile


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Workspace Profile Resolver")
    parser.add_argument("--workspace", help="Force specific workspace profile name (must exist in config.json profiles)")
    parser.add_argument("--path", help="Target repository directory path")
    parser.add_argument("--json", action="store_true", help="Output profile as JSON")
    args = parser.parse_args()

    profile = get_profile(workspace_name=args.workspace, target_path=args.path)

    if args.json:
        print(json.dumps(profile, indent=2, ensure_ascii=False))
    else:
        print(f"Active Workspace Profile: {profile['workspace_name']}")
        print(f"  Plane Host: {profile['plane_host']}")
        print(f"  Qdrant URL: {profile['qdrant_url']}")
        print(f"  Wiki Collection: {profile['qdrant_wiki_collection']}")
        print(f"  LLM Wiki Path: {profile['llm_wiki_path']}")
