#!/bin/bash
# context-usage-now.sh — on-demand ("pull") context-window usage measurement.
# Reads the transcript and prints current context length and percentage.
#
# Usage:
#   bash context-usage-now.sh [transcript_path]

SELFDIR="$(cd "$(dirname "$0")" && pwd)"
INJECT="$SELFDIR/context-usage-inject.sh"

TRANSCRIPT="$1"
if [ -z "$TRANSCRIPT" ]; then
  # Fallback: check ANTIGRAVITY log or latest Claude Code transcript
  if [ -n "$ANTIGRAVITY_AGENT" ] || [ -d "$HOME/.gemini/antigravity-cli/brain" ]; then
    TRANSCRIPT=$(find "$HOME/.gemini/antigravity-cli/brain" -name "transcript.jsonl" -type f -exec stat -f "%m %N" {} + 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)
  fi
  if [ -z "$TRANSCRIPT" ] && [ -d "$HOME/.claude/projects" ]; then
    TRANSCRIPT=$(find "$HOME/.claude/projects" -name "*.jsonl" -type f -exec stat -f "%m %N" {} + 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)
  fi
fi

if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
  echo "Error: transcript file not found." >&2
  exit 2
fi

# Normalize Windows / Git Bash /c/... path to C:/...
if [[ "$TRANSCRIPT" =~ ^/([a-zA-Z])/(.*) ]]; then
  DRIVE="${BASH_REMATCH[1]^^}"
  REST="${BASH_REMATCH[2]}"
  TRANSCRIPT="${DRIVE}:/${REST}"
fi

JSON_PAYLOAD=$(printf '{"transcript_path": "%s"}' "$TRANSCRIPT")

OUT=$(printf '%s' "$JSON_PAYLOAD" | bash "$INJECT")

if [ -z "$OUT" ]; then
  echo "Error: no usage data could be extracted from transcript: $TRANSCRIPT" >&2
  exit 2
fi

printf '%s\n' "$OUT"
