#!/usr/bin/env python3
"""Pre-push gate: catch hook-registry.yaml runtime-copy drift before it ships.

hook-registry.yaml (es6kr/claude-plugins, this repo's sibling checkout) lets
a hook entry declare a `runtime_copies` block: the canonical source path and
every filesystem root that is expected to carry a byte-identical copy of it
(plugin cache, symlinked marketplace clone, a personal ~/.agents mirror,
...). Nothing keeps those copies honest except a human remembering to run
`hook_registry_verify.py --check-copies` after touching the canonical file --
and a rebase or a concurrent session reintroducing a stale copy has already
happened more than once (see fix_plan.md's bash-guard.py drift history).

This script is the mechanical version of that reminder: when a push touches
a path any registry entry names as its `runtime_copies.canonical`, it shells
out to hook_registry_verify.py and blocks the push only on a COPY_DRIFT or
PARTIALLY_REMOVED finding for that entry -- never on an unrelated finding
elsewhere in the registry (--check validates the whole file, not just
copies), and never at all when the claude-plugins sibling checkout is not
present on this machine (soft-skip, not everyone has it cloned).

Deliberately has zero third-party dependencies (no PyYAML): the registry is
a small, regular subset of YAML here, so `extract_canonical_paths` is a
dependency-free line scanner instead -- mirroring hook_registry.py's own
"import-safe, no PyYAML" design (see that module's docstring). This keeps
this script's own test suite runnable under the CI pytest job, which
installs only pytest (.github/workflows/test.yml). PyYAML is only ever
needed by the hook_registry_verify.py subprocess this script may invoke,
exactly as documented in claude-plugins/hook-registry.md.

Usage (from .githooks/pre-push, one call per non-delete pushed ref):
    git diff --name-only "$SCAN_RANGE" | python3 scripts/check-runtime-copies-drift.py \
        --repo-root "$repo_root" \
        --plugins-root "${HOOK_REGISTRY_PLUGINS_ROOT:-$HOME/ghq/github.com/es6kr/claude-plugins}"

Changed file paths are read from stdin, one per line (relative to
--repo-root, the same shape `git diff --name-only` produces) -- not argv --
so this never has to worry about shell word-splitting a path with a space
in it.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys


def extract_canonical_paths(registry_text: str) -> set[str]:
    """Every `runtime_copies.canonical` path declared in hook-registry.yaml.

    Dependency-free line scanner, not a real YAML parser: hook-registry.yaml
    keeps a stable, regular block shape (2-space step per nesting level), so
    tracking "am I currently inside a runtime_copies: block" by indentation
    is enough. A `canonical:` key is only ever captured while inside such a
    block -- one at the same or shallower indent as an unrelated sibling key
    is ignored, and the block is considered closed the moment a line at or
    below the runtime_copies: line's own indent appears.
    """
    canonical_paths: set[str] = set()
    in_runtime_copies_block = False
    runtime_copies_indent = -1

    for raw_line in registry_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))

        if in_runtime_copies_block and indent <= runtime_copies_indent:
            in_runtime_copies_block = False

        if stripped == "runtime_copies:":
            in_runtime_copies_block = True
            runtime_copies_indent = indent
            continue

        if in_runtime_copies_block and stripped.startswith("canonical:"):
            value = stripped[len("canonical:"):].strip().strip("'\"")
            if value:
                canonical_paths.add(value)

    return canonical_paths


def touches_tracked_copy(changed_files, canonical_paths) -> bool:
    """True when any changed file is a runtime_copies-tracked canonical path."""
    return bool(set(changed_files) & set(canonical_paths))


def parse_changed_files(stdin_text: str) -> list[str]:
    return [line.strip() for line in stdin_text.splitlines() if line.strip()]


def build_verify_command(plugins_root: str, repo_root: str, verify_script: str) -> list[str]:
    return [
        "uv", "run", "--with", "pyyaml", "python", verify_script,
        "--check", "--check-copies",
        "--repo-root", repo_root,
        "--plugins-root", plugins_root,
    ]


def _run_subprocess(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def main(argv=None, stdin_text=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=os.getcwd())
    parser.add_argument(
        "--plugins-root",
        default=os.environ.get(
            "HOOK_REGISTRY_PLUGINS_ROOT",
            os.path.expanduser("~/ghq/github.com/es6kr/claude-plugins"),
        ),
        help="checkout of es6kr/claude-plugins, where hook-registry.yaml and "
        "hook_registry_verify.py now live (defaults to $HOOK_REGISTRY_PLUGINS_ROOT "
        "or the standard ghq path)",
    )
    args = parser.parse_args(argv)

    registry_path = os.path.join(args.plugins_root, "hook-registry.yaml")
    if not os.path.isfile(registry_path):
        print(
            "hook-registry copy-drift check skipped: no claude-plugins checkout "
            f"found at {args.plugins_root} (set HOOK_REGISTRY_PLUGINS_ROOT to "
            "override, or clone es6kr/claude-plugins there)",
            file=sys.stderr,
        )
        return 0

    changed_files = parse_changed_files(
        stdin_text if stdin_text is not None else sys.stdin.read()
    )

    with open(registry_path, encoding="utf-8") as fh:
        canonical_paths = extract_canonical_paths(fh.read())

    if not touches_tracked_copy(changed_files, canonical_paths):
        return 0

    verify_script = os.path.join(args.plugins_root, "scripts", "hook_registry_verify.py")
    if not os.path.isfile(verify_script):
        print(
            "hook-registry copy-drift check skipped: hook_registry_verify.py not "
            f"found under {args.plugins_root}/scripts",
            file=sys.stderr,
        )
        return 0

    if shutil.which("uv") is None:
        print(
            "hook-registry copy-drift check skipped: `uv` not found on PATH "
            "(required to run hook_registry_verify.py with PyYAML)",
            file=sys.stderr,
        )
        return 0

    cmd = build_verify_command(
        plugins_root=args.plugins_root, repo_root=args.repo_root, verify_script=verify_script
    )
    print(
        "Checking hook-registry.yaml runtime copy drift "
        "(uv run hook_registry_verify.py --check --check-copies)..."
    )
    result = _run_subprocess(cmd)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    if "COPY_DRIFT" in result.stdout or "PARTIALLY_REMOVED" in result.stdout:
        print(
            "\nERROR: this push changes a hook-registry.yaml runtime_copies-tracked "
            "file, and its deployed copies have drifted (see the COPY_DRIFT / "
            "PARTIALLY_REMOVED finding(s) above for which root). Sync every root "
            "listed in that entry's runtime_copies.expected_roots before pushing.\n"
            "See es6kr/claude-plugins hook-registry.md for the sync procedure.",
            file=sys.stderr,
        )
        return 1

    if result.returncode != 0:
        print(
            "\nwarning: hook_registry_verify.py reported findings unrelated to "
            "runtime-copy drift for the file(s) this push touches; not blocking "
            "this push on them.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
