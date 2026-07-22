#!/usr/bin/env bash
# plan-undecided-guard.sh — PostToolUse:Write|Edit guard
# After a plan-*.md (or *plan*.md) is written/edited, detect undecided markers
# and remind the assistant to run the "ask -> reflect -> auto-save" loop.
# Warning only (no blocking). Always exits 0.
#
# Responsible skill: code-workflow (resources holds the source). Install: ~/.claude/hooks/
# Recurrence target: failed-attempts.md "plan post-write undecided-items ask omitted" (2nd -> hook)
#
# Locale detection keywords live in ../data/*.regex (git-ignored, see opensource.md
# "Public repo locale-specific patterns"). If no data files exist the hook falls
# back to a built-in English-only pattern, so it never depends on the data dir.

INPUT="${CLAUDE_TOOL_INPUT:-$(cat)}"

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE_PATH" ] && exit 0

# Only target plan artifacts: plan-*.md, or paths containing plan + .md
case "$FILE_PATH" in
  *plan-*.md|*plan.md|*/plans/*.md|*/generated/*plan*.md) ;;
  *) exit 0 ;;
esac

# Read the saved plan file if available (PostToolUse: the file is already updated)
if [ -f "$FILE_PATH" ]; then
  BODY=$(cat "$FILE_PATH")
else
  # Fall back to the tool input written/edited chunk
  BODY=$(echo "$INPUT" | jq -r '(.tool_input.content // .tool_input.new_string) // empty' 2>/dev/null)
fi
[ -z "$BODY" ] && exit 0

# Undecided-marker detection (2 kinds):
#  (1) prose markers: placeholder / TBD / hold / X vs Y / decision required / recommend
#  (2) STRUCTURAL: a "Trade-offs / Alternatives" section heading or a comparison
#      table column (Option/Approach + Pros/Cons + Chosen). A clean ✅/✗ table has
#      no prose tokens and would evade (1), so the section's presence itself fires.
#      failed-attempts.md "Trade-offs section structural miss" (2026-06-26, 4th)
#
# Patterns load from ../data/*.regex (each non-empty, non-comment line is one
# alternation entry). The data/ dir is git-ignored so each user keeps their own
# locale patterns (en.regex, ko.regex, …). With no data files, fall back to the
# built-in English-only default.
DATA_DIR="$(dirname "$0")/../data"
if compgen -G "$DATA_DIR/*.regex" > /dev/null 2>&1; then
  PATTERN=$(cat "$DATA_DIR"/*.regex | sed 's/#.*$//' | awk 'NF' | paste -sd'|' -)
fi
if [ -z "${PATTERN:-}" ]; then
  PATTERN='___|\bTBD\b|decision required|deferred| vs |recommend|[Tt]rade-?offs?|[Aa]lternatives|\|[[:space:]]*Chosen|Pros[[:space:]]*\|.*Cons'
fi

MATCHES=$(echo "$BODY" | grep -nEi "$PATTERN" 2>/dev/null | head -8)

[ -z "$MATCHES" ] && exit 0

{
  echo "⚠️ [plan-undecided-guard] undecided markers detected in plan file: $FILE_PATH"
  echo "  matched lines:"
  echo "$MATCHES" | sed 's/^/    /'
  echo ""
  echo "  → HARD STOP loop (vibe-coding.md 'annotation cycle' + code-workflow steps.md 'Plan post-write ask'):"
  echo "     1. If the user request itself is an either/or ('do A or B'), that decision is the primary mandatory AskUserQuestion"
  echo "     2. Convert each undecided marker above into an AskUserQuestion option (questions array, 1 axis = 1 question)"
  echo "     3. On answer received → reflect 'Decision: X' into the plan file (Edit) + save"
  echo "     4. Re-grep to confirm 0 undecided markers, then report/proceed"
  echo ""
  echo "  A 'recommend' prose line is NOT a decision — user confirmation (AskUserQuestion) is required."
  echo "  See failed-attempts.md: 'plan post-write undecided-items ask omitted' (2026-05-27, 2nd)"
} >&2

exit 2
