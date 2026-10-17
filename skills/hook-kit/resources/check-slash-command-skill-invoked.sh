#!/usr/bin/env bash
# Stop event — verify that the most recent `/<slug>` slash-command invocation
# was followed by an actual Skill("<slug>", ...) tool_use call in the scoped
# window after it.
#
# Claude Code auto-injects the target skill's SKILL.md content into context
# when a `/<slug>` command is typed (`<command-name>/<slug></command-name>`),
# but that injection is not itself a tool call — the skill's procedure only
# starts once the assistant actually issues Skill("<slug>", ...). Seeing the
# injected content is easy to mistake for "already loaded, no call needed".
#
# Complements block-cleanup-without-claudify.sh, which only verifies the
# claudify sub-calls INSIDE an already-detected /cleanup run — it never
# checked for the top-level Skill("cleanup") call itself. This hook is the
# general top-level check for ANY slash command that maps to an installed
# skill (see failed-attempts.md "slash-command-inject-without-skill-call").
#
# Design notes:
#   - Anchors on the LAST genuine user-typed `<command-name>/<slug>` line in a
#     bounded recent window (mirrors block-cleanup-without-claudify.sh Gate B).
#   - Only checks slugs that resolve to an installed skill directory — native
#     Claude Code commands (/compact, /rename, /clear, /help, ...) and unknown
#     slugs are skipped to avoid false positives.
#   - `stop_hook_active` guard prevents an infinite block loop if the
#     reminder itself doesn't get acted on before the next Stop fires.
#
# Two registrations, one file (same shape as force-fa-on-correction-signal.sh):
#   UserPromptSubmit -> preventive. Injects a reminder BEFORE the model emits
#                       its first token, so the Skill call becomes the first
#                       tool call instead of being discovered missing later.
#   Stop             -> the check above, kept as the backstop. An injected
#                       reminder the model ignores is not a gate.

INPUT=$(cat)

if [[ "${RALPH_LOOP:-}" == "1" ]]; then exit 0; fi

# Only slugs that map to an actual installed skill are checked — native
# Claude Code commands and unrecognized slugs are skipped entirely.
skill_exists() {
  local slug="$1"
  [[ -d "$HOME/.claude/skills/$slug" ]] && return 0
  [[ -d "$HOME/.agents/skills/$slug" ]] && return 0
  find "$HOME/.claude/plugins/marketplaces" -mindepth 3 -maxdepth 5 -type d -name "$slug" -path "*/skills/*" 2>/dev/null | grep -q . && return 0
  return 1
}

EVENT=$(printf '%s' "$INPUT" | jq -r '.hook_event_name // empty' 2>/dev/null)
if [[ "$EVENT" == "UserPromptSubmit" ]]; then
  PROMPT=$(printf '%s' "$INPUT" | jq -r '.prompt // empty' 2>/dev/null)
  # Raw slash input ("/slug args") or an already-expanded <command-name> tag.
  # The slug must be followed by whitespace or end of input, so a path such
  # as "/mnt/c/..." is not mistaken for a command.
  RE_RAW='^[[:space:]]*/([a-zA-Z0-9_:-]+)([[:space:]]|$)'
  RE_TAG='<command-name>/([a-zA-Z0-9_:-]+)</command-name>'
  if [[ "$PROMPT" =~ $RE_RAW ]]; then
    SLUG="${BASH_REMATCH[1]}"
  elif [[ "$PROMPT" =~ $RE_TAG ]]; then
    SLUG="${BASH_REMATCH[1]}"
  else
    exit 0
  fi
  skill_exists "${SLUG##*:}" || exit 0
  jq -n --arg slug "$SLUG" '
    {
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext: "Slash command `/\($slug)` was typed. The skill text shown this turn is injected context, NOT an invocation. Make `Skill(\"\($slug)\", <args>)` your FIRST tool call this turn — before reading any topic file or running any step of the procedure. A Stop-time check verifies that the call happened."
      }
    }'
  exit 0
fi

STOP_HOOK_ACTIVE=$(printf '%s' "$INPUT" | jq -r 'if .stop_hook_active then "true" else "false" end' 2>/dev/null || echo "false")
if [[ "$STOP_HOOK_ACTIVE" == "true" ]]; then exit 0; fi

TRANSCRIPT_PATH=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
[[ -z "$TRANSCRIPT_PATH" || ! -f "$TRANSCRIPT_PATH" ]] && exit 0

# Search + staleness window (lines). Beyond this, treat the invocation as
# long-since resolved or abandoned — do not nag forever.
WINDOW=2000

TOTAL_LINES=$(wc -l < "$TRANSCRIPT_PATH" 2>/dev/null || echo 0)
[[ "$TOTAL_LINES" -eq 0 ]] && exit 0
START=$(( TOTAL_LINES > WINDOW ? TOTAL_LINES - WINDOW : 1 ))

# Last genuine user-typed slash-command line: excludes tool_result user-lines
# (quoting another session's invocation, e.g. RAG search hits), assistant
# lines (their inner quotes are JSON-escaped and never match this pattern),
# and compact-summary lines (`"isCompactSummary":true` — a summary's own
# narrative quotes prior turns verbatim, including a `<command-name>/<slug>`
# that was already invoked+resolved pre-compact; without this exclusion the
# stale quoted text reads identically to a live re-invocation).
CMD_MATCH=$(tail -n +"$START" "$TRANSCRIPT_PATH" 2>/dev/null \
  | grep -n '<command-name>/' \
  | grep '"type":"user"' \
  | grep -v 'tool_result' \
  | grep -v '"isCompactSummary":true' \
  | tail -1)
[[ -z "$CMD_MATCH" ]] && exit 0

REL_LINE="${CMD_MATCH%%:*}"
SLUG=$(printf '%s' "$CMD_MATCH" | grep -oE '<command-name>/[a-zA-Z0-9_:-]+</command-name>' | head -1 \
  | sed -E 's#<command-name>/([a-zA-Z0-9_:-]+)</command-name>#\1#')
[[ -z "$SLUG" ]] && exit 0

BASE_SLUG="${SLUG##*:}"

skill_exists "$BASE_SLUG" || exit 0

ABS_LINE=$(( START + REL_LINE - 1 ))
SCOPED=$(tail -n +"$ABS_LINE" "$TRANSCRIPT_PATH" 2>/dev/null)

# Require actual assistant Skill tool_use structure, not an unrelated input
# object or quoted text. Bare calls remain compatible with namespaced commands,
# but two explicitly different namespaces must never satisfy each other.
if printf '%s' "$SCOPED" | jq -s -e --arg slug "$SLUG" --arg base "$BASE_SLUG" '
  any(.[];
    .type == "assistant" and
    any(.message.content? | select(type == "array") | .[];
      .type == "tool_use" and .name == "Skill" and
      (.input.skill? | select(type == "string") |
        . == $slug or . == $base or
        (($slug | contains(":")) | not) and (split(":") | last) == $base
      )
    )
  )
' >/dev/null 2>&1; then
  exit 0
fi

jq -n --arg slug "$SLUG" '
  {
    decision: "block",
    reason: "Detected `/\($slug)` typed by the user, but no `Skill(\"\($slug)\", ...)` tool_use call was found afterward in this transcript. A slash-command inject (the SKILL.md content shown after `/\($slug)`) is NOT itself a Skill invocation — it only surfaces the skill'\''s instructions; the procedure starts only once the assistant actually calls the Skill tool. If `/\($slug)`'\''s procedure was already followed manually this turn, call `Skill(\"\($slug)\")` now anyway to record the formal invocation before proceeding."
  }'
exit 0
