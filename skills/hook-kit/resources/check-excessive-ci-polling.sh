#!/usr/bin/env bash
# PreToolUse hook wrapper for check-excessive-ci-polling.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/check-excessive-ci-polling.py" "$@"
