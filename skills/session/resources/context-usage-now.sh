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
  # Claude Code encodes a workspace's cwd into its project dir name by
  # replacing every '/' and '.' character in the absolute cwd with '-'.
  # Try THIS workspace's own project dir first, before any Antigravity check:
  # a cwd-scoped match is the strongest signal of "this call belongs to a
  # Claude Code session for this specific workspace", and it must outrank a
  # mere "the Antigravity brain dir exists somewhere on this machine" check --
  # on any machine where both harnesses have ever run, that existence check
  # is true unconditionally and previously stole precedence away from Claude
  # Code every time, regardless of which harness actually invoked this script.
  if [ -d "$HOME/.claude/projects" ]; then
    PROJECT_KEY=$(printf '%s' "$PWD" | tr '/.' '-')
    PROJECT_DIR="$HOME/.claude/projects/$PROJECT_KEY"
    if [ -d "$PROJECT_DIR" ]; then
      TRANSCRIPT=$(find "$PROJECT_DIR" -maxdepth 1 -name "*.jsonl" -type f -exec stat -f "%m %N" {} + 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)
    fi
  fi
  # Fallback: check ANTIGRAVITY log
  if [ -z "$TRANSCRIPT" ] && { [ -n "$ANTIGRAVITY_AGENT" ] || [ -d "$HOME/.gemini/antigravity-cli/brain" ]; }; then
    TRANSCRIPT=$(find "$HOME/.gemini/antigravity-cli/brain" -name "transcript.jsonl" -type f -exec stat -f "%m %N" {} + 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)
  fi
  # Last-resort global Claude Code search -- only when this workspace has no
  # project dir yet (e.g. a brand-new cwd) AND no Antigravity transcript was
  # found either. Globbing across every project under ~/.claude/projects
  # picks whichever session (this machine or another, synced in via
  # Syncthing) happens to have the newest mtime globally -- with many
  # concurrent sessions across workspaces/machines that is effectively a
  # coin flip, and it silently reports a completely unrelated session's
  # usage as this caller's own, so it is the last resort, not the default.
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
