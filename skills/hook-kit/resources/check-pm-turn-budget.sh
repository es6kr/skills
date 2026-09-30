#!/usr/bin/env bash
# PostToolUse hook wrapper for check-pm-turn-budget.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/check-pm-turn-budget.py" "$@"
