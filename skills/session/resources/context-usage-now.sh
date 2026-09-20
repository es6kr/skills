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
  find_newest_transcript() {
    local search_dir="$1"
    local name_pat="$2"
    local maxdepth="${3:-}"
    [ -d "$search_dir" ] || return 0

    if stat -f "%m" /dev/null >/dev/null 2>&1; then
      if [ -n "$maxdepth" ]; then
        find "$search_dir" -maxdepth "$maxdepth" -name "$name_pat" -type f -exec stat -f "%m %N" {} + 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-
      else
        find "$search_dir" -name "$name_pat" -type f -exec stat -f "%m %N" {} + 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-
      fi
    elif stat -c "%Y" /dev/null >/dev/null 2>&1; then
      if [ -n "$maxdepth" ]; then
        find "$search_dir" -maxdepth "$maxdepth" -name "$name_pat" -type f -exec stat -c "%Y %n" {} + 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-
      else
        find "$search_dir" -name "$name_pat" -type f -exec stat -c "%Y %n" {} + 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-
      fi
    else
      python3 -c "
import os, sys, glob
sdir, pat, md = sys.argv[1], sys.argv[2], sys.argv[3]
matched = []
if md:
    try:
        for f in os.listdir(sdir):
            if glob.fnmatch.fnmatch(f, pat):
                p = os.path.join(sdir, f)
                if os.path.isfile(p):
                    matched.append(p)
    except OSError:
        pass
else:
    for root, _, files in os.walk(sdir):
        for f in files:
            if glob.fnmatch.fnmatch(f, pat):
                matched.append(os.path.join(root, f))
if matched:
    print(max(matched, key=os.path.getmtime))
" "$search_dir" "$name_pat" "$maxdepth" 2>/dev/null
    fi
  }

  raw_agy_app_dir="${ANTIGRAVITY_APP_DATA_DIR:-$HOME/.gemini/antigravity-cli}"
  norm_agy_app_dir="${raw_agy_app_dir//\\//}"
  local_agy_brain="$norm_agy_app_dir/brain"

  is_agy_active=0
  if [ -n "$ANTIGRAVITY_AGENT" ] || [ -n "$ANTIGRAVITY_CONVERSATION_ID" ]; then
    is_agy_active=1
  fi

  # 1. Antigravity Environment Check:
  # When running under an active Antigravity session (ANTIGRAVITY_AGENT or
  # ANTIGRAVITY_CONVERSATION_ID is explicitly set in the environment),
  # Antigravity MUST take absolute precedence over any stale Claude Code
  # project directory that happens to exist for the same workspace cwd.
  if [ "$is_agy_active" -eq 1 ]; then
    if [ -n "$ANTIGRAVITY_CONVERSATION_ID" ] && [ -f "$local_agy_brain/$ANTIGRAVITY_CONVERSATION_ID/.system_generated/logs/transcript.jsonl" ]; then
      TRANSCRIPT="$local_agy_brain/$ANTIGRAVITY_CONVERSATION_ID/.system_generated/logs/transcript.jsonl"
    elif [ -n "$ANTIGRAVITY_CONVERSATION_ID" ] && [ -d "$local_agy_brain/$ANTIGRAVITY_CONVERSATION_ID" ]; then
      TRANSCRIPT=$(find_newest_transcript "$local_agy_brain/$ANTIGRAVITY_CONVERSATION_ID" "transcript.jsonl" 4)
    elif [ -d "$local_agy_brain" ]; then
      TRANSCRIPT=$(find_newest_transcript "$local_agy_brain" "transcript.jsonl" 4)
    fi
  fi

  # 2. Claude Code Project Directory Check:
  # Try THIS workspace's own project dir next (only if Antigravity is not active):
  # a cwd-scoped match is the strongest signal of "this call belongs to a
  # Claude Code session for this specific workspace", outranking unconfigured
  # background Antigravity directory checks.
  if [ "$is_agy_active" -eq 0 ] && [ -z "$TRANSCRIPT" ] && [ -d "$HOME/.claude/projects" ]; then
    PROJECT_KEY=$(printf '%s' "$PWD" | tr '/.' '-')
    PROJECT_DIR="$HOME/.claude/projects/$PROJECT_KEY"
    if [ -d "$PROJECT_DIR" ]; then
      TRANSCRIPT=$(find_newest_transcript "$PROJECT_DIR" "*.jsonl" 1)
    fi
  fi

  # 3. Fallback: unconfigured Antigravity check
  if [ -z "$TRANSCRIPT" ] && [ -d "$local_agy_brain" ]; then
    TRANSCRIPT=$(find_newest_transcript "$local_agy_brain" "transcript.jsonl" 4)
  fi

  # 4. Last-resort global Claude Code search -- only when this workspace has no
  # project dir yet (e.g. a brand-new cwd) AND no Antigravity transcript was
  # found either. Only allowed if Antigravity is not active.
  if [ "$is_agy_active" -eq 0 ] && [ -z "$TRANSCRIPT" ] && [ -d "$HOME/.claude/projects" ]; then
    TRANSCRIPT=$(find_newest_transcript "$HOME/.claude/projects" "*.jsonl")
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
