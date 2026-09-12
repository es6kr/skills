#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — Block an ask issued in place of a direct answer
# when the user's last message is a direct question.
#
# Background: "user asks a question -> assistant fires AskUserQuestion instead
# of answering" recurred 5 times (failed-attempts "direct answer first" family,
# idx 70). Escalation policy mandates a hook at 3+ recurrences; this hook is
# the 5th-recurrence enforcement.
#
# Contract (answer-first):
#   1. Last real user text (skips tool_result / system-injected entries)
#      matches a question signal — trailing "?" in any language, or Korean
#      interrogative endings supplied via data/hangul-patterns.regex.
#   2. Assistant text emitted AFTER that message totals < MIN_ANSWER_CHARS.
#   Both true -> exit 2 (block) with answer-first guidance.
#
# Escape: answer the question in plain text first (>= MIN_ANSWER_CHARS since
# the question); the same AskUserQuestion call then passes unchanged.

INPUT=$(cat)

# Ralph autonomous loop never asks — exempt for symmetry with sibling guards.
if [[ "${RALPH_LOOP:-}" == "1" ]]; then exit 0; fi

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" == "AskUserQuestion" ]] || exit 0
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
[[ -n "$TRANSCRIPT_PATH" && -f "$TRANSCRIPT_PATH" ]] || exit 0

# Locale patterns (git-ignored data file; English-only fallback below).
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then . "$HG_DATA_FILE"; fi
QSIG="${HG_QSIG_INTERROGATIVE:-\\?[[:space:]]*$}"

MIN_ANSWER_CHARS=80

# One pass over the transcript tail:
#   lu    = index of the last real user text entry
#   alen  = total assistant text length after that entry
#   atu   = count of assistant tool_use blocks (excluding AskUserQuestion) after it
#   qtail = last 200 chars of the user text (question signals sit at the end)
#
# atu exemption (structural-FP fix): when answer text and the ask land in the
# SAME assistant message, that message is not yet flushed to the transcript at
# PreToolUse time — alen undercounts and a legitimate answer-first call gets
# blocked. Investigation tool calls after the question ARE flushed, so atu >= 1
# means "mid-flight work turn whose final text is invisible" -> do not block.
# This narrows the hook to its real target: the reflexive question -> immediate
# ask with no intervening answer or investigation.
STATE=$(tail -n 400 "$TRANSCRIPT_PATH" 2>/dev/null | jq -rs '
  def text_of(m):
    if (m|type) != "object" then ""
    elif ((m.content?)|type) == "string" then m.content
    elif ((m.content?)|type) == "array"
      then ([m.content[] | select(.type? == "text") | .text] | join(" "))
    else "" end;
  def tools_of(m):
    if (m|type) != "object" then 0
    elif ((m.content?)|type) == "array"
      then ([m.content[] | select(.type? == "tool_use" and .name? != "AskUserQuestion")] | length)
    else 0 end;
  [ .[] | select(type=="object") | {t: .type, x: text_of(.message // {}), tu: tools_of(.message // {})} ] as $e
  | ([ range(0; ($e|length))
      | select($e[.].t == "user"
               and (($e[.].x | length) > 0)
               and (($e[.].x | startswith("<")) | not)
               and (($e[.].x | startswith("[")) | not)) ] | max // -1) as $lu
  | if $lu < 0 then "NOUSER\t0\t0\t"
    else
      ([ $e[($lu+1):][] | select(.t=="assistant") | .x ] | join(" ") | length) as $alen
      | ([ $e[($lu+1):][] | select(.t=="assistant") | .tu ] | add // 0) as $atu
      | "OK\t\($alen)\t\($atu)\t\($e[$lu].x[-200:] | gsub("[\\t\\n]"; " "))"
    end
' 2>/dev/null)

[[ -n "$STATE" ]] || exit 0
MARK=$(printf '%s' "$STATE" | cut -f1)
[[ "$MARK" == "OK" ]] || exit 0
ANS_LEN=$(printf '%s' "$STATE" | cut -f2)
ATU_CNT=$(printf '%s' "$STATE" | cut -f3)
Q_TAIL=$(printf '%s' "$STATE" | cut -f4-)

# Mid-flight work turn: investigation tool calls after the question mean the
# final (unflushed) message may carry the answer — skip to avoid structural FP.
case "${ATU_CNT:-0}" in (*[!0-9]*) ATU_CNT=0;; esac
if [[ "$ATU_CNT" -ge 1 ]]; then exit 0; fi

# Question signal: trailing "?" (any language) OR locale interrogative ending.
IS_Q=0
if printf '%s' "$Q_TAIL" | grep -qE '\?[[:space:]"]*$'; then IS_Q=1; fi
if [[ "$IS_Q" -eq 0 ]] && printf '%s' "$Q_TAIL" | grep -qE "$QSIG"; then IS_Q=1; fi
[[ "$IS_Q" -eq 1 ]] || exit 0

case "${ANS_LEN:-0}" in (*[!0-9]*) exit 0;; esac
if [[ "$ANS_LEN" -ge "$MIN_ANSWER_CHARS" ]]; then exit 0; fi

cat >&2 <<'EOF'
[hook:block-ask-on-question-signal] BLOCKED (exit 2)

The user's last message is a direct question, but no direct answer text has
been emitted before this AskUserQuestion call.

Answer-first contract (5th recurrence of "question -> ask evasion"):
  1. Answer the question directly in plain text FIRST — state the fact,
     assessment, or recommendation the user asked for.
  2. Only after answering, re-issue the ask IF a genuine user decision
     remains. The same AskUserQuestion call passes once the answer text
     since the question reaches 80+ characters.

Do not rephrase the user's question into options to avoid answering it.
EOF
exit 2
