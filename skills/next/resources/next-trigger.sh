#!/bin/bash
# next-trigger.sh — Stop hook for next skill
#
# Detects task completion keywords in the last assistant message and emits
# a skill-trigger marker so that the LLM invokes the `next` skill in its
# follow-up response.
#
# Besides the keyword scan, two blind-spot guards fire unconditionally:
#   1. Tool-call-only ending — the last assistant message has zero text blocks
#      (e.g. the turn ended on a bare ScheduleWakeup call). No text = no report
#      to the user AND the keyword scan can never match, so this is always a
#      defect signal.
#   2. Waiting-turn ending — the last assistant message registered a
#      ScheduleWakeup (polling/wait handoff). Control returns to the user for a
#      long window, so follow-up options are due even without a completion
#      keyword.
#
# Trigger condition: Stop hook fires when Claude finishes a response.
# Input (stdin): JSON { session_id, transcript_path, stop_hook_active }
# Output (stdout): on match, a JSON Stop-hook decision object of the form
#   {"decision":"block","reason":"<skill-trigger name=\"next\">…</skill-trigger>"}
# (the skill-trigger marker is embedded inside the JSON `reason` field — it is
# NOT emitted as a bare standalone marker, because Stop hooks deliver stdout to
# the debug log only; the `decision:"block"` envelope is what surfaces the
# `reason` text to the LLM. See ~/.claude/skills/hook/SKILL.md "Output channel
# spec per event"). On no match, output is empty.
#
# Responsibility: next skill (per automation.md "Hook responsibility policy").
# Install: copy to ~/.claude/hooks/next-trigger.sh and register in
# ~/.claude/settings.json under "Stop" matcher (see next/SKILL.md Install).

set -euo pipefail

INPUT="$(cat)"

# JSON parsing uses jq (a hook-wide dependency — the trigger dispatchers all use it).
# Do NOT use `python3` here: on Windows Git Bash `python3` is often the Microsoft
# Store stub, which silently no-ops and leaves this hook permanently dormant.
TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // ""' 2>/dev/null || echo "")

STOP_HOOK_ACTIVE=$(printf '%s' "$INPUT" | jq -r 'if .stop_hook_active then "true" else "false" end' 2>/dev/null || echo "false")

DEBUG_LOG="$(dirname "$0")/next-trigger.debug.log"

# Prevent infinite loops: do not re-trigger when this hook itself caused the stop.
# OBSERVABILITY (next-invocation family, 12th recurrence): this suppression used to
# exit with NO log line, hiding the fact that EVERY later stop of a continuation
# chain (a turn resumed from an earlier Stop-hook block) is silently skipped by the
# harness — exactly the window where the "next call missed" family recurs on long
# chained turns. The suppression itself cannot be bypassed (loop prevention is the
# point); log it so the gap is diagnosable from evidence instead of guesses.
if [[ "$STOP_HOOK_ACTIVE" == "true" ]]; then
  { printf '%s\tsuppressed=stop_hook_active\ttranscript=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$TRANSCRIPT" >> "$DEBUG_LOG"; } 2>/dev/null || true
  exit 0
fi

if [[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]]; then
  { printf '%s\tearly_exit=no_transcript\ttranscript=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$TRANSCRIPT" >> "$DEBUG_LOG"; } 2>/dev/null || true
  exit 0
fi

# Extract concatenated text of the most recent assistant message from JSONL.
# IMPORTANT: A single response is split into multiple text blocks (between tool_use
# blocks). We must concatenate ALL text blocks of the LAST message — not overwrite
# with each block, which captures only the trailing fragment (often non-completion).
# See ~/.agents/rules/failed-attempts.md "Hook last_text missed multiple text-blocks".
# jq pipeline (python3-free — see note above). Stage 1 (`jq -R 'fromjson? // empty'`)
# tolerantly parses each JSONL line, skipping any malformed line (mirrors the old
# per-line try/except). Stage 2 slurps, takes the LAST assistant message's uuid, and
# concatenates every text block across assistant lines sharing that uuid — so a single
# response split into multiple text blocks (between tool_use blocks) is fully captured.
#
# SCOPE: everything after the last real user prompt — i.e. the whole current
# turn — NOT just the last assistant entry's uuid group. A turn that emits text
# and then ends on a tool call is written as TWO assistant entries with
# DIFFERENT uuids (text entry, then tool_use-only entry). Scoping to the last
# uuid therefore saw an empty text and fired the "tool-call-only" guard below on
# turns that did report to the user (observed twice in one session, 2026-07-24).
# `tool_result` entries also carry type=="user", so the anchor accepts only user
# entries whose content is a STRING (a real prompt); tool_result content is an
# array. Mirrors block-ask-on-question-signal.sh's anchor.
LAST_TEXT=$(jq -R 'fromjson? // empty' "$TRANSCRIPT" 2>/dev/null | jq -rs '
  [ .[] | select(type == "object") ] as $e
  | if ($e | length) == 0 then ""
    else
      ([ range(0; ($e | length))
         | select($e[.].type == "user" and (($e[.].message.content? | type) == "string")) ] | max // -1) as $lu
      | [ $e[($lu + 1):][]
          | select(.type == "assistant")
          | (.message.content // [])[] | select(.type == "text") | .text ]
      | join("\n")
    end
' 2>/dev/null || echo "")

# Tool names used by the last assistant message (same uuid group) — needed for
# the waiting-turn guard below.
LAST_TOOLS=$(jq -R 'fromjson? // empty' "$TRANSCRIPT" 2>/dev/null | jq -rs '
  [ .[] | select(.type == "assistant") ] as $a
  | if ($a | length) == 0 then ""
    else
      ($a | last | .uuid // "") as $u
      | [ $a[] | select((.uuid // "") == $u) | (.message.content // [])[] | select(.type == "tool_use") | .name ]
      | join(",")
    end
' 2>/dev/null || echo "")

# Blind-spot guard 1 — tool-call-only ending (no final text at all).
# A turn that stops without any user-facing text is always a reporting defect:
# the final message must carry the report. Empty text also means the keyword
# scan below can never fire, so this exact case (e.g. ending on a bare
# ScheduleWakeup call) silently bypassed the trigger before this guard.
# The LAST_TOOLS check distinguishes a genuine tool-call-only message from an
# empty/assistant-less transcript (both yield empty LAST_TEXT).
if [[ -z "$LAST_TEXT" && -n "$LAST_TOOLS" ]]; then
  echo '{"decision":"block","reason":"<skill-trigger name=\"next\">Turn ended with a tool-call-only message (no final text). Emit a final status report for the user; if a task batch completed or control returns to the user (e.g. waiting on CI/wakeup), invoke the `next` skill to offer follow-up options.</skill-trigger>"}'
  exit 0
fi

# Blind-spot guard 2 — waiting-turn ending: the final message registered a
# ScheduleWakeup (polling/wait handoff). Control returns to the user for a long
# window, so follow-up options are due even without a completion keyword.
if [[ ",${LAST_TOOLS}," == *",ScheduleWakeup,"* ]]; then
  echo '{"decision":"block","reason":"<skill-trigger name=\"next\">Waiting-turn detected (ScheduleWakeup registered in the final message). Ensure a final status report was given, then invoke the `next` skill to offer interim follow-up options while waiting.</skill-trigger>"}'
  exit 0
fi

# Completion keyword detection (case-insensitive).
# Patterns are loaded from data/*.regex files — each non-empty, non-comment line
# is concatenated into a single egrep -E alternation. The data/ directory is
# git-ignored (skills/next/.gitignore) and publish-ignored (.clawhubignore),
# so each user adds their own locale patterns (en.regex, ko.regex, ja.regex…).
# If no data files exist, fall back to a built-in English default.
DATA_DIR="$(dirname "$0")/../data"
if compgen -G "$DATA_DIR/*.regex" > /dev/null 2>&1; then
  PATTERN=$(cat "$DATA_DIR"/*.regex | sed 's/#.*$//' | awk 'NF' | paste -sd'|' -)
else
  PATTERN='Fix complete:|✅|all done|^[[:space:]]*done\.|task (complete|completed|finished)|completed[\.\!\)\*,[:space:]]|finished[\.\!\)\*,[:space:]]|wrapped up'
fi

MATCHED="false"
if echo "$LAST_TEXT" | grep -qiE "$PATTERN"; then
  MATCHED="true"
fi

# Diagnostics (HARD STOP rationale) — this hook's "next skill call missed" failure mode
# has recurred 9+ times (see failed-attempts.md) with every prior fix guessing at regex
# content, because there was no evidence trail proving whether the hook even ran or
# what LAST_TEXT it actually extracted. A 2026-07-22 session confirmed the ko.regex
# pattern DID match the live completion text, yet no decision:block ever surfaced —
# meaning the failure is upstream (dispatch/transcript-read timing), not content. This
# log lets the next occurrence be diagnosed from hard evidence instead of another guess.
{
  printf '%s\ttranscript=%s\tlast_text_len=%s\tmatched=%s\tsnippet=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$TRANSCRIPT" "${#LAST_TEXT}" "$MATCHED" \
    "$(printf '%s' "$LAST_TEXT" | tr '\n' ' ' | cut -c1-80)" >> "$DEBUG_LOG"
  # Rotate: Stop fires every turn, so cap growth — keep the last 200 entries.
  if [[ "$(wc -l < "$DEBUG_LOG" 2>/dev/null || echo 0)" -gt 500 ]]; then
    tail -n 200 "$DEBUG_LOG" > "$DEBUG_LOG.tmp" && mv "$DEBUG_LOG.tmp" "$DEBUG_LOG"
  fi
} 2>/dev/null || true

if [[ "$MATCHED" == "true" ]]; then
  # Output JSON decision:"block" — Stop hook spec: stdout goes to debug log only;
  # JSON decision:"block" prevents stop and feeds reason to Claude as a follow-up signal.
  # See ~/.claude/skills/hook/SKILL.md "Output channel spec per event".
  echo '{"decision":"block","reason":"<skill-trigger name=\"next\">Task completion signal detected. Invoke the `next` skill to suggest follow-up actions.</skill-trigger>"}'
fi

exit 0
