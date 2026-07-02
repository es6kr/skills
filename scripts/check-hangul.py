#!/usr/bin/env python3
"""check-hangul.py — Verify no Korean text remains in skill directories before publishing.

Usage:
    python3 check-hangul.py [skills-parent-dir]
    python3 check-hangul.py <skill-dir1> [skill-dir2] ...

Two invocation modes:
    (1) Parent mode: pass a single directory containing skill subdirs (e.g., `skills`).
        Iterates each immediate subdir as a skill.
    (2) Explicit mode: pass one or more individual skill directories
        (detected by the presence of SKILL.md in the path).

Scans all .md and .sh files for Korean characters (Hangul Syllables, U+AC00..U+D7A3).

Exit codes:
    0 = all clean (or no skill subdirs found in parent mode)
    1 = Korean text found, or invalid argument (non-directory)

This implementation deliberately avoids `grep` so behavior is identical on macOS,
Linux, and CI regardless of shell aliases / functions / wrappers (e.g., a
ugrep-as-grep wrapper that applies `--ignore-files`).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# Force UTF-8 output regardless of the console's locale encoding. Windows
# consoles default to cp949/cp1252, which raise UnicodeEncodeError when printing
# the ✓/✗ glyphs or matched Korean lines — silently turning a "Korean found"
# verdict into an unrelated crash. CI (UTF-8 locale) is unaffected.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover — non-reconfigurable stream
        pass

# ANSI colors — match the original bash script's output exactly.
RED = "\033[0;31m"
GREEN = "\033[0;32m"
NC = "\033[0m"

# Hangul Syllables block. Compose programmatically so the source file
# itself contains no Korean characters (passes check-hangul on its own repo).
HANGUL_RE = re.compile(f"[{chr(0xAC00)}-{chr(0xD7A3)}]")

SCAN_EXTS = (".md", ".sh")
MAX_MATCHES_PRINTED = 5


def _is_skill_dir(path: Path) -> bool:
    """A skill directory contains a SKILL.md at its top level."""
    return (path / "SKILL.md").is_file()


def _scan_dir(skill_dir: Path) -> list[tuple[Path, int, str]]:
    """Return a list of (file, line_number, line_text) for every line with Hangul."""
    matches: list[tuple[Path, int, str]] = []
    for root, _dirs, files in os.walk(skill_dir):
        for name in files:
            if not name.endswith(SCAN_EXTS):
                continue
            file_path = Path(root) / name
            try:
                with file_path.open("r", encoding="utf-8", errors="replace") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if HANGUL_RE.search(line):
                            matches.append((file_path, lineno, line.rstrip("\n")))
            except OSError as exc:  # pragma: no cover — unreadable file is exceptional
                print(f"WARN: could not read {file_path}: {exc}", file=sys.stderr)
    matches.sort(key=lambda m: (str(m[0]), m[1]))
    return matches


def _tracked_skill_names(parent: Path) -> set[str] | None:
    """Return the set of skill subdirs (immediate children of ``parent``) that
    are tracked by git. Return None when git is unavailable or ``parent`` is
    outside a git repo — the caller then falls back to scanning every subdir.

    Only the FIRST path component under ``parent`` is used, so a single tracked
    file inside ``skills/<name>/`` marks the whole skill as tracked.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--", str(parent)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except (OSError, FileNotFoundError):
        return None
    if proc.returncode != 0:
        return None

    # git ls-files emits POSIX paths relative to the repo root. Normalise the
    # parent to POSIX form and strip it as a prefix from each entry.
    try:
        parent_rel = parent.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        parent_rel = parent.as_posix()
    prefix = parent_rel.rstrip("/") + "/"

    tracked: set[str] = set()
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(prefix):
            rel = line[len(prefix):]
        elif "/" in line and parent.name and line.startswith(parent.name + "/"):
            rel = line[len(parent.name) + 1:]
        else:
            continue
        head = rel.split("/", 1)[0]
        if head:
            tracked.add(head)
    return tracked


def _resolve_targets(argv: list[str]) -> list[Path]:
    """Resolve CLI args into a list of skill directories to scan.

    Mirrors the original shell script:
      - No args → default to ``skills``.
      - One arg that is a directory without a top-level SKILL.md → treat as parent,
        expand to immediate subdirectories.
      - Otherwise → each arg must be a directory; treat as an explicit skill dir.
    """
    if not argv:
        argv = ["skills"]

    # Parent mode detection: single arg, directory, no SKILL.md at top level.
    if len(argv) == 1:
        candidate = Path(argv[0])
        if candidate.is_dir() and not (candidate / "SKILL.md").is_file():
            subdirs = sorted(p for p in candidate.iterdir() if p.is_dir())
            if not subdirs:
                print(f"No skill subdirs found under: {candidate}")
                sys.exit(0)
            # Tracked-only filter: when candidate lives inside a git repo,
            # restrict to skill subdirs that are actually tracked. Untracked
            # local-only skills (in-development, personal, or not yet published)
            # are not subject to the publish-time hangul gate. See
            # ~/.agents/.claude/rules/release-please-scope.md "Staging branch
            # flow" for the sibling policy applied to frontmatter lint.
            tracked = _tracked_skill_names(candidate)
            if tracked is not None:
                subdirs = [p for p in subdirs if p.name in tracked]
                if not subdirs:
                    print(f"No tracked skill subdirs to scan under: {candidate}")
                    sys.exit(0)
            return subdirs

    # Explicit mode: validate every arg is a directory.
    targets: list[Path] = []
    for arg in argv:
        path = Path(arg)
        if not path.is_dir():
            print(f"Not a directory: {arg}")
            sys.exit(1)
        targets.append(path)
    return targets


def main(argv: list[str]) -> int:
    targets = _resolve_targets(argv)
    has_hangul = False

    for skill_dir in targets:
        name = skill_dir.name or str(skill_dir)
        matches = _scan_dir(skill_dir)
        if matches:
            has_hangul = True
            print(f"{RED}✗{NC} {name} — {len(matches)} Korean lines found")
            for file_path, lineno, line in matches[:MAX_MATCHES_PRINTED]:
                print(f"{file_path}:{lineno}:{line}")
            print()
        else:
            print(f"{GREEN}✓{NC} {name} — clean")

    if has_hangul:
        print(f"\n{RED}BLOCKED: Korean text found. Translate before publishing.{NC}")
        return 1

    print(f"\n{GREEN}All skills clean. Ready to publish.{NC}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
