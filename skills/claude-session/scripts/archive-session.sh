#!/usr/bin/env bash
# archive-session.sh — Move a session jsonl out of an active project key
#                     to ~/.claude/.archive/<project-key>/<uuid>.jsonl
#
# Usage: archive-session.sh <session-uuid>
#        archive-session.sh <session-uuid> --dry-run

set -euo pipefail

SESSION_ID="${1:-}"
DRY_RUN=0
if [[ "${2:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

if [[ -z "$SESSION_ID" ]]; then
  echo "Usage: $(basename "$0") <session-uuid> [--dry-run]" >&2
  exit 64
fi

# Locate the source file
SRC=$(find "$HOME/.claude/projects" -maxdepth 2 -name "${SESSION_ID}.jsonl" -type f 2>/dev/null | head -1)
if [[ -z "$SRC" ]]; then
  echo "ERROR: session not found anywhere under ~/.claude/projects: $SESSION_ID" >&2
  exit 1
fi

PROJECT_KEY=$(basename "$(dirname "$SRC")")
DST_DIR="$HOME/.claude/.archive/$PROJECT_KEY"
DST="$DST_DIR/${SESSION_ID}.jsonl"

# Safety checks
if [[ ! -s "$SRC" ]]; then
  echo "ERROR: source is empty (use /session purge instead): $SRC" >&2
  exit 1
fi

if [[ -e "$DST" ]]; then
  echo "ERROR: destination already exists: $DST" >&2
  echo "       Manual resolution required." >&2
  exit 1
fi

# Detect if this is the currently active session via the SessionStart inject hook env
if [[ -n "${CLAUDE_SESSION_ID:-}" && "${CLAUDE_SESSION_ID}" == "$SESSION_ID" ]]; then
  echo "ERROR: $SESSION_ID is the currently active session — refusing to archive." >&2
  echo "       Close the session in Claude Code first, then re-run." >&2
  exit 1
fi

# Report
SIZE=$(wc -c < "$SRC" | tr -d ' ')
LINES=$(wc -l < "$SRC" | tr -d ' ')
echo "Will archive:"
echo "  FROM: $SRC"
echo "  TO:   $DST"
echo "  SIZE: $SIZE bytes, $LINES lines"
echo "  PROJ: $PROJECT_KEY"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "(dry-run — no changes made)"
  exit 0
fi

# Execute
mkdir -p "$DST_DIR"
mv "$SRC" "$DST"

# Verify
if [[ -f "$DST" && ! -f "$SRC" ]]; then
  echo "OK: archived"
else
  echo "FAIL: post-move verification mismatch" >&2
  exit 2
fi

# Append to ledger
LEDGER="$HOME/.claude/.archive/INDEX.md"
if [[ ! -f "$LEDGER" ]]; then
  cat > "$LEDGER" <<'EOF'
# Claude Code Session Archive Index

Each entry: `- YYYY-MM-DD <project-key>/<uuid> — <custom-title or empty>`

EOF
fi

# Pick up a custom-title if the session had one
TITLE=""
if command -v jq >/dev/null 2>&1; then
  TITLE=$(jq -r 'select(.type=="custom-title") | .customTitle // empty' "$DST" 2>/dev/null | head -1 || true)
fi
echo "- $(date +%Y-%m-%d) $PROJECT_KEY/$SESSION_ID — ${TITLE:-(no custom-title)}" >> "$LEDGER"

echo "Ledger updated: $LEDGER"
