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

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE_PATH" ] && exit 0

# Only target one-shot plan ARTIFACTS in their established directories:
#   docs/generated/plan-*.md, .ralph/docs/generated/plan-*.md, .omc/plans/*.md
# NOT the fix-plan tracker family (fix_plan.md, checklist.md) — those are a
# distinct, persistent, multi-session artifact class owned by the fix-plan
# skill, where [BLOCKED]/deferred markers are the intended long-lived state,
# not an unresolved decision awaiting this turn's AskUserQuestion. A bare
# `*plan.md` substring glob previously matched `fix_plan.md` by accident
# (the `*` absorbs the `fix_` prefix) and re-litigated months of already-
# resolved history on every unrelated edit.
# The `*docs/generated/plan-*.md` arm alone already matches any path ending
# in that suffix regardless of what precedes it (including a `.ralph/` or
# `.omc/`-style prefix), so a dedicated `.ralph` arm would be unreachable —
# kept as a single arm instead of a redundant/dead second branch. No leading
# `/` is required before `docs`/`.omc` so the match still holds even if
# FILE_PATH is ever a bare relative path with no directory prefix at all
# (Write/Edit's file_path is documented as always-absolute in practice, so
# this is defense-in-depth rather than a live bug).
case "$FILE_PATH" in
  *docs/generated/plan-*.md|*.omc/plans/*.md) ;;
  *) exit 0 ;;
esac

case "$TOOL_NAME" in
  Write)
    # A Write is a fresh full-file replace — whole-file scan is equivalent to
    # a diff scan (there is no "prior content" distinct from what was written).
    BODY=$(echo "$INPUT" | jq -r '.tool_input.content // empty' 2>/dev/null)
    ;;
  Edit)
    # An Edit only changes a slice of a file that may span many prior turns
    # or sessions. Scanning the whole file re-fires on markers that were
    # already resolved by an earlier ask-cycle. Scope to the new content only.
    BODY=$(echo "$INPUT" | jq -r '.tool_input.new_string // empty' 2>/dev/null)
    ;;
  *)
    exit 0
    ;;
esac
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

# Drop code-reference lines before reporting.
# A line that cites source locations (`file.ts:120-127`, `L45`) is describing WHERE
# something lives, not leaving a decision open — " vs " inside such a line compares
# two code sites, not two options. Without this filter the guard blocks on prose like
# "uuid set `validation.ts:72-77` vs skip logic `86-88`", which has no decision in it.
MATCHES=$(printf '%s\n' "$MATCHES" | grep -vE '`[^`]*\.(ts|tsx|js|jsx|py|sh|md|json|ya?ml)[^`]*`|`[^`]*:[0-9]+(-[0-9]+)?`|\bL[0-9]+(-L?[0-9]+)?\b' || true)

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
