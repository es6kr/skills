#!/usr/bin/env bash
# Required skill metadata gate: root and nested tracked plugin sources.
# Usage: bash scripts/lint-frontmatter.sh [repository-or-skill-tree]
# Reuse SkillSpector; do not maintain another YAML/length implementation here.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
LINTER="$repo_root/skills/skill-kit/scripts/skillspector_lint.py"
ROOT="${1:-$repo_root}"
PY=""
for candidate in "${PYTHON:-}" python3 python; do
  [[ -n "$candidate" ]] || continue
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import yaml' >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done
if [[ -z "$PY" ]]; then
  echo "BLOCKED: Python with PyYAML is required (requirements-lint.txt)." >&2
  exit 1
fi
exec "$PY" "$LINTER" --frontmatter-only --require-version --tracked "$ROOT"
