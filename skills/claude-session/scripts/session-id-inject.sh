#!/usr/bin/env bash
# session-id-inject.sh — Inject session/message context only when the current
# prompt asks for it (regex match on the prompt body).
#
# Usage: bash session-id-inject.sh [EventName]
#   - EventName defaults to "UserPromptSubmit"
#   - SessionStart is also supported but no-ops by default (use this hook on
#     UserPromptSubmit; the previous SessionStart registration was removed).
#
# Prompt patterns:
#   /(claude-)?session id ...                  → session UUID + transcript (legacy parity)
#   /<namespace> (qdrant-)?import ...          → session UUID + transcript + current message UUID
#   /cleanup [run]                             → same as import (cleanup's 3-C.1 calls RAG import)
#   anything else                              → exit 0 (no injection — saves context tokens)
#
# Keyword fallback rationale: when the user types "search qdrant" / "was this
# session saved" / etc. without an explicit slash command, the LLM still needs the
# current session UUID to query or correlate RAG chunks. Cheaper to inject
# proactively than to make the LLM guess the session UUID via heuristics (mtime
# of JSONLs is unreliable across split/compact). Per user request 2026-05-28.
#
# IMPORTANT: When adding a new caller that invokes the RAG import topic,
# update this regex AND the RAG import skill's matching pattern documentation.

EVENT_NAME="${1:-UserPromptSubmit}"
INPUT=$(cat)

SESSION_ID=$(jq -r '.session_id // empty' <<< "$INPUT" 2>/dev/null)
TRANSCRIPT=$(jq -r '.transcript_path // empty' <<< "$INPUT" 2>/dev/null)
PROMPT=$(jq -r '.prompt // empty' <<< "$INPUT" 2>/dev/null)
PROMPT_ID=$(jq -r '.prompt_id // empty' <<< "$INPUT" 2>/dev/null)

# Unix path conversion (Windows backslash + drive letter)
TRANSCRIPT_UNIX=""
if [[ -n "$TRANSCRIPT" ]]; then
  TRANSCRIPT_UNIX=$(echo "$TRANSCRIPT" | sed 's|\\|/|g; s|^C:|/c|')
fi

emit_session_only() {
  local extra="$1"
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "${EVENT_NAME}",
    "additionalContext": "Current session ID: ${SESSION_ID}\nTranscript: ${TRANSCRIPT_UNIX:-unknown}${extra}\nUse this session ID and transcript path for /session repair, etc. Do not search for them.\nTo rename this session, use the /rename built-in command (do NOT call rename-session.sh, which is only for other sessions by ID)."
  }
}
EOF
}

# Extract the most recent user message uuid from JSONL if prompt_id is absent.
# UserPromptSubmit usually fires after the prompt is appended; the tail-based
# lookup is the robust fallback.
resolve_message_uuid() {
  if [[ -n "$PROMPT_ID" ]]; then
    echo "$PROMPT_ID"
    return
  fi
  if [[ -n "$TRANSCRIPT_UNIX" && -f "$TRANSCRIPT_UNIX" ]]; then
    jq -r 'select(.type == "user" and (.message.content | type == "string")) | .uuid' \
      "$TRANSCRIPT_UNIX" 2>/dev/null | tail -1
  fi
}

# Guard: bail if we don't even have a session id
[[ -z "$SESSION_ID" ]] && exit 0

# SessionStart path: no-op by default (the inject is now on UserPromptSubmit).
# Kept as a safety net in case the hook is still wired to SessionStart.
if [[ "$EVENT_NAME" == "SessionStart" ]]; then
  exit 0
fi

# Branch on the prompt body. Use bash regex (BASH_REMATCH-free, presence only).
if [[ "$PROMPT" =~ ^/(claude-)?session[[:space:]]+id([[:space:]]|$) ]]; then
  emit_session_only ""
  exit 0
fi

if [[ "$PROMPT" =~ ^/[a-zA-Z0-9_-]+[[:space:]]+(qdrant-)?import([[:space:]]|$) ]] || \
   [[ "$PROMPT" =~ ^/cleanup($|[[:space:]]run([[:space:]]|$)) ]]; then
  MUUID=$(resolve_message_uuid)
  if [[ -n "$MUUID" ]]; then
    emit_session_only "\nCurrent message UUID: ${MUUID}"
  else
    # Still emit session info; flag that uuid lookup failed so the LLM falls back
    emit_session_only "\nCurrent message UUID: (unresolved — check JSONL tail)"
  fi
  exit 0
fi

# Keyword fallback: prompt body mentions "qdrant", "rag", or "session" (case-insensitive).
# Triggers proactive session-id injection so the LLM does not guess via mtime.
# Excludes the slash-command syntax already handled above. Word-boundary-ish
# match to keep false positives low (avoids matching "obsession" / random
# substrings — we want the bare word).
if echo "$PROMPT" | grep -qiE '(^|[^A-Za-z])(qdrant|rag|session)([^A-Za-z]|$)'; then
  emit_session_only ""
  exit 0
fi

# Default: no injection.
exit 0
