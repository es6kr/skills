#!/usr/bin/env python3
"""check_marketplace_cache_drift.py — detect scripts present in a plugin marketplace
checkout but missing from an installed plugin's cache.

Claude Code installs a plugin by copying its marketplace checkout into a pinned
per-version cache directory (`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`).
That cache is not auto-synced when the marketplace checkout moves forward (new
commits on the tracked branch) — a script added or moved in the marketplace after
the cache snapshot was taken silently goes missing from the installed copy, and a
hook/skill that recommends `~/.claude/plugins/cache/.../scripts/<name>.py` becomes
a dead end for any session that only looks at the cache.

This is a *reporting* tool, not a fixer — it surfaces drift so it can be triaged
(re-install the plugin, or note the specific missing file) rather than papering
over it silently. Standard library only — run under bare `python3`, no venv.

Usage:
  python3 check_marketplace_cache_drift.py                 # scan every installed plugin
  python3 check_marketplace_cache_drift.py --plugin es6kr  # scan one plugin (name@marketplace or bare name)
  python3 check_marketplace_cache_drift.py --json           # machine-readable output
"""
import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_EXTS = (".py", ".js", ".sh")
SCRIPT_DIRS = ("scripts", "resources")


def default_claude_dir():
    return Path.home() / ".claude"


def load_installed_plugins(claude_dir):
    path = claude_dir / "plugins" / "installed_plugins.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data.get("plugins", {})


def marketplace_checkout_dir(claude_dir, marketplace_name):
    path = claude_dir / "plugins" / "marketplaces" / marketplace_name
    return path if path.is_dir() else None


def load_plugin_sources(marketplace_dir):
    """Map plugin name -> declared `source` from the marketplace's own
    `.claude-plugin/marketplace.json`. A marketplace can bundle several
    plugins at different subpaths (source: "./plugins/ralph", etc.) rather
    than exposing its whole repo root as a single plugin — scanning the repo
    root for every plugin would attribute every *other* bundled plugin's
    scripts to this one as false "missing" entries.
    """
    path = marketplace_dir / ".claude-plugin" / "marketplace.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        p.get("name"): p.get("source", "./")
        for p in data.get("plugins", [])
        if p.get("name")
    }


def resolve_scan_root(marketplace_dir, source):
    """Resolve a marketplace.json `source` value ("./", "./plugins/x", ...)
    to an absolute path under marketplace_dir."""
    source = source or "./"
    if source in ("./", "."):
        return marketplace_dir
    if source.startswith("./"):
        source = source[2:]
    return marketplace_dir / source


EXCLUDED_DIR_NAMES = {".worktrees", ".git", "node_modules", ".bak"}


def find_scripts(scan_root):
    """Every skills/<skill>/{scripts,resources}/*.{py,js,sh} file under scan_root,
    at any nesting depth. Returns paths relative to scan_root.

    Uses os.walk with topdown pruning (not Path.glob("**/...")) so excluded
    directories — nested git worktrees (`.worktrees/<branch>/...`) checked out
    inside the marketplace repo itself, `.git`, `node_modules` — are never
    descended into. On a slow filesystem (e.g. a WSL /mnt/c mount) a repo with
    several worktrees checked out can make an unpruned recursive glob take
    minutes; pruning keeps this a sub-second check.
    """
    found = []
    for root, dirs, files in os.walk(scan_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIR_NAMES]
        rel_root = Path(root).relative_to(scan_root)
        parts = rel_root.parts
        if parts and parts[-1] in SCRIPT_DIRS and "skills" in parts[:-1]:
            for name in files:
                if name.endswith(SCRIPT_EXTS):
                    found.append(rel_root / name)
    return sorted(set(found))


def audit_plugin(claude_dir, plugin_key, installs):
    """Return a dict report for one 'name@marketplace' plugin entry, or None if the
    marketplace checkout itself is unavailable (nothing to compare against)."""
    if "@" not in plugin_key:
        return None
    plugin_name, marketplace_name = plugin_key.split("@", 1)
    marketplace_dir = marketplace_checkout_dir(claude_dir, marketplace_name)
    if marketplace_dir is None:
        return {
            "plugin": plugin_key,
            "marketplace_checkout": None,
            "missing": [],
            "error": f"marketplace checkout not found: {marketplace_name}",
        }

    sources = load_plugin_sources(marketplace_dir)
    source = sources.get(plugin_name, "./")
    if not isinstance(source, str):
        # Some marketplaces (e.g. claude-plugins-official) declare a plugin's
        # source as an object pointing at an *external* repo/commit
        # (`{"source": "git-subdir", "url": ..., "path": ...}` or
        # `{"source": "url", "url": ...}`) rather than a local subpath of
        # this same checkout. There is nothing under marketplace_dir to
        # compare the cache against in that case.
        return {
            "plugin": plugin_key,
            "marketplace_checkout": str(marketplace_dir),
            "error": (
                f"plugin source is external ({source.get('source', 'unknown') if isinstance(source, dict) else source!r})"
                " — not a local subpath of this marketplace checkout, skipping"
            ),
        }
    scan_root = resolve_scan_root(marketplace_dir, source)

    marketplace_scripts = find_scripts(scan_root)
    missing_by_install = []
    for install in installs:
        install_path = install.get("installPath")
        if not install_path:
            continue
        cache_root = Path(install_path)
        if not cache_root.is_dir():
            missing_by_install.append({
                "cache_path": install_path,
                "error": "cache installPath does not exist",
                "missing_scripts": [],
            })
            continue
        missing = [
            str(rel) for rel in marketplace_scripts
            if not (cache_root / rel).exists()
        ]
        missing_by_install.append({
            "cache_path": install_path,
            "missing_scripts": missing,
        })

    return {
        "plugin": plugin_key,
        "marketplace_checkout": str(marketplace_dir),
        "scan_root": str(scan_root),
        "installs": missing_by_install,
    }


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--claude-dir", default=None, help="Override ~/.claude (for testing)")
    ap.add_argument("--plugin", default=None,
                     help="Scan only this plugin — bare name (e.g. 'es6kr') or 'name@marketplace'")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    claude_dir = Path(args.claude_dir) if args.claude_dir else default_claude_dir()
    plugins = load_installed_plugins(claude_dir)
    if not plugins:
        print(f"No installed_plugins.json found (or empty) under {claude_dir}", file=sys.stderr)
        return 1

    if args.plugin:
        if "@" in args.plugin:
            keys = [args.plugin] if args.plugin in plugins else []
        else:
            keys = [k for k in plugins if k.split("@", 1)[0] == args.plugin]
        if not keys:
            print(f"No installed plugin matching {args.plugin!r}", file=sys.stderr)
            return 1
    else:
        keys = list(plugins.keys())

    reports = []
    for key in keys:
        report = audit_plugin(claude_dir, key, plugins[key])
        if report is not None:
            reports.append(report)

    if args.json:
        print(json.dumps(reports, indent=2))
        return 0 if not _any_missing(reports) else 1

    any_drift = False
    for report in reports:
        if report.get("error"):
            print(f"[{report['plugin']}] SKIP — {report['error']}")
            continue
        for install in report.get("installs", []):
            if install.get("error"):
                print(f"[{report['plugin']}] SKIP install — {install['error']}")
                continue
            missing = install["missing_scripts"]
            if not missing:
                continue
            any_drift = True
            print(f"[{report['plugin']}] cache={install['cache_path']}")
            for rel in missing:
                print(f"  MISSING: {rel}")

    if not any_drift:
        print("No drift detected — every marketplace script exists in its plugin's cache.")
    return 1 if any_drift else 0


def _any_missing(reports):
    for report in reports:
        if report.get("error"):
            continue
        for install in report.get("installs", []):
            if install.get("missing_scripts"):
                return True
    return False


if __name__ == "__main__":
    sys.exit(main())
