#!/usr/bin/env bash
# PreToolUse:AskUserQuestion + PreToolUse:Skill — Block a Ralph-supervisor session
# from recommending or directly invoking Ralph's own pipeline work
# (consolidate / pr-review / github-flow merge / code-review), instead of fixing
# the rule so the next autonomous Ralph loop applies it.
#
# Background: agent-coord.md "supervisor != Ralph loop" recurrence
# family. 1st (2026-05-04) / 2nd (2026-05-07) / 3rd (2026-05-11) / 4th (2026-06-12,
# AskUserQuestion option recommending Skill("consolidate","pr-review")) / 5th
# (2026-07-17, this hook's origin — supervisor about to run pipeline Skill calls
# directly). 4th occurrence already mandated this hook; it was deferred until now.
# See: ~/.claude/skills/cleanup/data/failed-attempts.md "supervisor session directly
# executing Ralph-loop work" (5th recurrence).
#
# Scope note: this hook intentionally does NOT block plain read-only `gh pr view`
# / `gh pr list` Bash calls — those are too broad a signal (used constantly for
# legitimate context-gathering) and would cause high false positives. It blocks
# the two concrete manifestations seen across all 5 occurrences: (a) an
# AskUserQuestion option recommending Ralph's pipeline work, (b) a direct
# Skill("consolidate"|"github-flow", ...) invocation — both only when supervisor
# context is detected AND RALPH_LOOP is not set (i.e., this is an interactive
# supervising session, not the Ralph autonomous loop itself).

INPUT=$(cat)

# Ralph's own autonomous loop is exempt — this hook only guards interactive
# supervisor sessions doing Ralph's job themselves.
if [[ "${RALPH_LOOP:-}" == "1" ]]; then
  exit 0
fi

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)

# Locale detection patterns live in git-ignored data/ (Korean + English). The hook
# carries an English-only fallback so the PUBLIC copy works without the data file.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
[ -f "$HG_DATA_FILE" ] && . "$HG_DATA_FILE"
HG_SUPERVISOR_CONTEXT="${HG_SUPERVISOR_CONTEXT:+${HG_SUPERVISOR_CONTEXT}|}ralph.{0,20}supervis|supervis.{0,20}ralph"

# Ralph-supervisor context detection: the USER asked for ralph supervision.
# Scoped to real user text entries only — raw-transcript grep false-positived on
# (a) the system-injected agent-type listing (the "ralph:ralph-supervisor" Ralph
# supervisor-agent entry) and (b) assistant text quoting that listing (2026-07-18
# interactive /wip session mis-flagged as supervisor). Filters: skip
# tool_result-only entries, <system-reminder>-wrapped injections, bracketed
# interrupt markers, and any text carrying the agent-registry listing signature.
SUPERVISOR_CONTEXT=0
if [[ -n "$TRANSCRIPT_PATH" && -f "$TRANSCRIPT_PATH" ]]; then
  USER_TEXTS=$(tail -n 400 "$TRANSCRIPT_PATH" 2>/dev/null | jq -r '
    select(type=="object" and .type=="user")
    | .message.content
    | if type == "string" then .
      elif type == "array" then ([.[] | select(.type? == "text") | .text] | join(" "))
      else "" end
    | select(length > 0)
    | select(startswith("<system-reminder") | not)
    | select(startswith("[") | not)
    | select(contains("Available agent types") | not)
    | select(contains("ralph:ralph-supervisor:") | not)
  ' 2>/dev/null)
  if printf '%s' "$USER_TEXTS" | grep -qiE "$HG_SUPERVISOR_CONTEXT"; then
    SUPERVISOR_CONTEXT=1
  fi
fi

if [[ "$SUPERVISOR_CONTEXT" -eq 0 ]]; then
  exit 0
fi

TRIGGER_KEYWORDS='consolidate|pr-review|/consolidate|/github-flow merge|code-reviewer|github-flow.*pr\b'

case "$TOOL_NAME" in
  AskUserQuestion)
    COMBINED=$(echo "$INPUT" | jq -r '
      .tool_input.questions[]? | .options[]? | ((.label // "") + " " + (.description // ""))
    ' 2>/dev/null)
    if [[ -z "$COMBINED" ]]; then
      exit 0
    fi
    if echo "$COMBINED" | grep -qiE "$TRIGGER_KEYWORDS"; then
      cat >&2 <<EOF
[hook:block-supervisor-loop-work] BLOCKED (exit 2)

A Ralph-supervisor session tried to recommend Ralph pipeline work
(consolidate/pr-review/github-flow merge/code-review) in an AskUserQuestion option.

agent-coord.md "supervisor != Ralph" principle: a supervisor session only does
BLOCKED classification + rule fixes. Running the pipeline is the next autonomous
Ralph loop's job.

Correct flow: (1) if a rule is wrong, fix PROMPT.md/fix_plan.md
(2) the next Ralph loop applies the fixed rule itself.

This pattern has recurred 5+ times. Do not bypass; proceed via the rule-fix path.
Detail: ~/.claude/skills/cleanup/data/failed-attempts.md "supervisor session directly
executing Ralph-loop work — 5th recurrence"
EOF
      exit 2
    fi
    ;;
  Skill)
    SKILL_NAME=$(echo "$INPUT" | jq -r '.tool_input.skill // .tool_input.name // empty' 2>/dev/null)
    if echo "$SKILL_NAME" | grep -qiE '^(consolidate|github-flow)$'; then
      ARGS=$(echo "$INPUT" | jq -r '.tool_input.args // empty' 2>/dev/null)
      if [[ "$SKILL_NAME" == "consolidate" ]] || echo "$ARGS" | grep -qiE 'merge|pr-review'; then
        cat >&2 <<EOF
[hook:block-supervisor-loop-work] BLOCKED (exit 2)

A Ralph-supervisor session tried to directly invoke a Ralph pipeline
Skill(\`$SKILL_NAME\`). This violates the agent-coord.md "supervisor != Ralph"
principle — execution is the next autonomous Ralph loop's job. Fix the rule and wait.

This pattern has recurred 5+ times.
Detail: ~/.claude/skills/cleanup/data/failed-attempts.md "supervisor session directly
executing Ralph-loop work — 5th recurrence"
EOF
        exit 2
      fi
    fi
    ;;
esac

exit 0
