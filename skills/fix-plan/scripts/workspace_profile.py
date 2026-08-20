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

# Config file locations, newest first. v2 names roles ("rag", "backlog") and
# carries the vendor in a `kind` field, so swapping a vendor is a one-line
# config edit. v1 named the vendor in the key itself. Consumers of this module
# still read the v1-shaped flat keys, so v2 is translated down to them here —
# a v2 file that reached consumers untranslated would look like an empty
# profile and hand every caller the placeholder defaults.
CONFIG_FILE = Path.home() / ".config" / "plane-backlog" / "config.json"
CONFIG_FILE_V2 = Path.home() / ".config" / "agent-workspace" / "config.json"

DEFAULT_PROFILE = {
    "workspace_name": "default",
    "plane_host": "",
    "plane_token_env": "PLANE_API_KEY",
    "qdrant_url": "http://localhost:6333",
    "qdrant_wiki_collection": "wiki",
    "qdrant_memory_collection": "claude-memory",
    "qdrant_task_collection": "fix-plan",
    "llm_wiki_path": "",
    "default_project": "default",
    "tracker_root": ".ralph"
}


def v2_profile_to_flat(profile: dict, defaults: dict) -> dict:
    """Translate one v2 role-shaped profile into the v1 flat keys.

    A role set to kind "none" means "not configured for this workspace", which
    must surface as an empty value rather than falling through to
    DEFAULT_PROFILE's placeholder (localhost) — otherwise "unconfigured" and
    "configured, pointing at localhost" become indistinguishable downstream.
    """
    roles = dict(defaults or {})
    roles.update(profile.get("roles") or {})
    flat = {}

    match = profile.get("match") or {}
    if match.get("path_components"):
        flat["cwd_match"] = match["path_components"]
    elif profile.get("cwd_match"):
        flat["cwd_match"] = profile["cwd_match"]

    backlog = roles.get("backlog") or {}
    if backlog.get("kind", "none") != "none":
        flat["plane_host"] = backlog.get("endpoint", "")
        flat["plane_token_env"] = backlog.get("token_env", "PLANE_API_KEY")
        flat["default_project"] = backlog.get("project", "")
    else:
        flat["plane_host"] = ""

    rag = roles.get("rag") or {}
    if rag.get("kind", "none") != "none":
        flat["qdrant_url"] = rag.get("endpoint", "")
        for key, value in (rag.get("collections") or {}).items():
            flat["qdrant_%s_collection" % key] = value
    else:
        flat["qdrant_url"] = ""

    wiki = roles.get("wiki") or {}
    if wiki.get("kind") == "git" and wiki.get("path"):
        flat["llm_wiki_path"] = wiki["path"]

    checklist = roles.get("checklist") or {}
    if checklist.get("kind") == "file" and checklist.get("path"):
        parent = str(Path(checklist["path"]).parent)
        if parent not in ("", "."):
            flat["tracker_root"] = parent

    return flat


def load_user_config():
    """Load the first available user config, translating v2 down to v1 keys.

    v2 wins when present; v1 stays readable for the migration window so a
    machine that has not been migrated keeps working unchanged.
    """
    for path in (CONFIG_FILE_V2, CONFIG_FILE):
        if not path.exists():
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: failed to parse {path}: {e}", file=sys.stderr)
            continue
        if not isinstance(cfg, dict):
            continue
        profiles = cfg.get("profiles") or {}
        is_v2 = any(
            isinstance(p, dict) and "roles" in p for p in profiles.values()
        )
        if is_v2:
            defaults = cfg.get("defaults") or {}
            cfg = {
                "profiles": {
                    # workspace_name must be carried explicitly: DEFAULT_PROFILE
                    # already holds "default" for that key, so get_profile's
                    # setdefault cannot correct it later.
                    name: dict(v2_profile_to_flat(p, defaults), workspace_name=name)
                    for name, p in profiles.items()
                    if isinstance(p, dict)
                }
            }
        return cfg
    return {}


def token_matches(token: str, parts) -> bool:
    """True if `token` matches a contiguous run of path segments in `parts`.

    Tokens are written in two shapes: a bare component ("es6kr") and a path
    fragment ("ghq/github.com/es6kr"). Splitting on "/" and comparing segment
    sequences handles both.

    Comparing whole segments (rather than substrings) is what keeps a token
    like "es6kr" from also matching an unrelated sibling such as
    "not-es6kr-workspace" — that property must survive any change here.
    """
    seq = [s for s in str(token).split("/") if s]
    if not seq:
        return False
    n = len(seq)
    return any(list(parts[i:i + n]) == seq for i in range(len(parts) - n + 1))


def detect_workspace(target_path: str = None) -> str:
    """Detect workspace profile based on env var, explicit path, or cwd match against configured profiles."""
    profiles = load_user_config().get("profiles", {})

    # 1. Environment variable override
    env_profile = os.environ.get("PLANE_WORKSPACE_PROFILE")
    if env_profile in profiles:
        return env_profile

    # 2. Check path against each configured profile's cwd_match tokens.
    # Tokens may be a bare component or a multi-segment fragment; see token_matches.
    cwd = Path(target_path or os.getcwd()).resolve()
    cwd_parts = cwd.parts

    for name, cfg in profiles.items():
        for token in cfg.get("cwd_match", [name]):
            if token_matches(token, cwd_parts):
                return name

    # 3. No match — "default" only. Do NOT fall back to an arbitrary configured profile;
    # that would silently target the wrong workspace's Plane token/Qdrant collection.
    return "default"


def resolve_tracker_root(target_path: str = None, workspace_name: str = None) -> str:
    """Resolve the tracker root directory (the dir holding fix_plan.md) for a workspace.

    Priority:
      1. FIXPLAN_TRACKER_ROOT env var (per-invocation override, aids testing)
      2. The workspace profile's explicit "tracker_root" (config.json profiles.<name>)
      3. Filesystem auto-detect: ".agents/fix_plan.md" then ".ralph/fix_plan.md"
      4. ".ralph" default (backward-compatible with Ralph workspaces)

    Note: step 2 reads the RAW configured value, not the merged DEFAULT_PROFILE, so a
    workspace that does not set "tracker_root" falls through to auto-detect rather than
    being pinned to ".ralph".

    workspace_name, when given, takes precedence over re-detecting from target_path —
    callers that already resolved an explicit/forced workspace (e.g. get_profile's
    --workspace override) must keep using that same workspace here.
    """
    env_root = os.environ.get("FIXPLAN_TRACKER_ROOT")
    if env_root:
        return env_root

    profiles = load_user_config().get("profiles", {})
    name = workspace_name or detect_workspace(target_path)
    configured = profiles.get(name, {}).get("tracker_root")
    if configured:
        return configured

    base = Path(target_path or os.getcwd()).resolve()
    for candidate in (".agents", ".ralph"):
        if (base / candidate / "fix_plan.md").exists():
            return candidate

    return ".ralph"


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

    # Resolve the tracker root dynamically (env > raw config > auto-detect > ".ralph"),
    # overriding the static DEFAULT_PROFILE value so consumers get the real root.
    profile["tracker_root"] = resolve_tracker_root(target_path, workspace_name=name)

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
        print(f"  Tracker Root: {profile['tracker_root']}")
