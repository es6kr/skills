#!/usr/bin/env bash
#
# graph-stop-evaluator.sh: Stop hook wrapper for Graph-State Stop Cleanup Evaluator
# Evaluates session DAG status on Stop events and performs safe low-risk auto-drain.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ES6KR_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
AGENTS_ROOT="${ES6KR_ROOT}/.agents"

if [[ ! -d "${AGENTS_ROOT}" ]]; then
  # Fallback if invoked outside es6kr root
  AGENTS_ROOT="${HOME}/.agents"
fi

RUNNER="${AGENTS_ROOT}/graph/scripts/run_stop_evaluator.py"

if [[ ! -f "${RUNNER}" ]]; then
  exit 0
fi

# Execute evaluator in auto-drain mode (sub-100ms)
PYTHONPATH="${AGENTS_ROOT}" python3 "${RUNNER}" \
  --workspace "${ES6KR_ROOT}" \
  --auto-drain \
  --format summary 2>&1 || true

exit 0
