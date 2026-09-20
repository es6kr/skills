#!/usr/bin/env bash
# resolve-session-id.sh — Deterministic, race-condition-free Claude Code session resolution.
# Matches session JSONL files by delivered prompt payload or unique marker, rather than
# relying on fragile mtime (ls -t) heuristics that collide in multi-session environments.
#
# Usage:
#   resolve-session-id.sh --payload "<prompt_text>" [--project-dir <path>] [--json] [--timeout-secs <N>]
#   resolve-session-id.sh --marker "<marker>" [--project-dir <path>] [--json]

set -euo pipefail

CLAUDE_PROJECTS_DIR="${HOME}/.claude/projects"

PAYLOAD=""
MARKER=""
PROJECT_DIR=""
TIMEOUT_SECS=1
EMIT_JSON=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --payload)
      PAYLOAD="$2"
      shift 2
      ;;
    --marker)
      MARKER="$2"
      shift 2
      ;;
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --timeout-secs)
      TIMEOUT_SECS="$2"
      shift 2
      ;;
    --json)
      EMIT_JSON=1
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: resolve-session-id.sh --payload "<text>" [options]

Options:
  --payload <text>       Exact prompt text or substring delivered to the session
  --marker <marker>      Unique marker string (alias for --payload)
  --project-dir <dir>    Explicit Claude projects directory (defaults to auto-derived from CWD)
  --timeout-secs <N>     Maximum seconds to wait for JSONL file flush (default: 1)
  --json                 Output JSON with ok, sessionId, sessid8, and jsonl path
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

TARGET_TEXT="${PAYLOAD:-$MARKER}"
if [[ -z "$TARGET_TEXT" ]]; then
  echo "Error: --payload or --marker is required" >&2
  exit 2
fi

cwd_to_project_name() {
    local cwd="$1"
    cwd="${cwd%/}"
    echo "$cwd" | sed 's/[^a-zA-Z0-9]/-/g'
}

# Resolve project directory if not specified
if [[ -z "$PROJECT_DIR" ]]; then
  PROJECT_NAME=$(cwd_to_project_name "$(pwd)")
  PROJECT_DIR="$CLAUDE_PROJECTS_DIR/$PROJECT_NAME"

  if [[ ! -d "$PROJECT_DIR" ]]; then
    SEARCH_DIR="$(pwd)"
    while [[ "$SEARCH_DIR" != "/" ]]; do
      SEARCH_DIR=$(dirname "$SEARCH_DIR")
      CANDIDATE="$CLAUDE_PROJECTS_DIR/$(cwd_to_project_name "$SEARCH_DIR")"
      if [[ -d "$CANDIDATE" ]]; then
        PROJECT_DIR="$CANDIDATE"
        break
      fi
    done
  fi
fi

if [[ ! -d "$PROJECT_DIR" ]]; then
  if (( EMIT_JSON )); then
    echo '{"ok":false,"error":"Project directory not found"}'
  else
    echo "Error: Project directory not found: $PROJECT_DIR" >&2
  fi
  exit 1
fi

# Search with timeout polling
start_time=$(date +%s)
matched_file=""

while true; do
  # Find all candidate JSONLs containing TARGET_TEXT as a literal fixed string
  # (exclude sync-conflict files). Ambiguous matches are a hard error, not a
  # mtime-based guess -- multiple sessions containing the same payload text
  # must be disambiguated by the caller via a unique --marker, never silently
  # resolved to "whichever file is newest" (that reintroduces the exact race
  # this resolver exists to eliminate).
  matches=$(grep -Frl -- "$TARGET_TEXT" "$PROJECT_DIR"/*.jsonl 2>/dev/null | grep -vF 'sync-conflict' || true)
  match_count=$(printf '%s\n' "$matches" | grep -c . || true)

  if [[ "$match_count" -eq 1 ]]; then
    matched_file="$matches"
    break
  elif [[ "$match_count" -gt 1 ]]; then
    if (( EMIT_JSON )); then
      echo "{\"ok\":false,\"error\":\"Ambiguous payload match: $match_count session files contain the same text. Use --marker with a unique per-delivery value to disambiguate.\"}"
    else
      {
        echo "Error: Ambiguous payload match ($match_count session files contain the same text)."
        echo "Use --marker with a unique per-delivery value to disambiguate. Candidates:"
        echo "$matches"
      } >&2
    fi
    exit 1
  fi

  now=$(date +%s)
  if (( now - start_time >= TIMEOUT_SECS )); then
    break
  fi
  sleep 0.5
done

if [[ -z "$matched_file" ]]; then
  if (( EMIT_JSON )); then
    echo "{\"ok\":false,\"error\":\"No session file found containing payload in $PROJECT_DIR\"}"
  else
    echo "Error: No session file found containing payload: $TARGET_TEXT in $PROJECT_DIR" >&2
  fi
  exit 1
fi

SESSION_ID=$(basename "$matched_file" .jsonl)
SESSID8="${SESSION_ID:0:8}"

if (( EMIT_JSON )); then
  node -e '
    const [sessionId, sessid8, jsonl, projectDir] = process.argv.slice(1);
    console.log(JSON.stringify({
      ok: true,
      sessionId,
      sessid8,
      jsonl,
      projectDir
    }, null, 2));
  ' "$SESSION_ID" "$SESSID8" "$matched_file" "$PROJECT_DIR"
else
  echo "$SESSION_ID"
fi
