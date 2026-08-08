#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — Block axis-merged single-question with multiple finding types
#
# Trigger: AskUserQuestion called with questions.length == 1 AND options
#          containing 2+ distinct finding-type keywords (Refactor/Tip/Nitpick/
#          Critical/Important/Minor) or 2+ distinct file:line identifiers.
# Action: Deny with guidance to split into multiple questions in the questions array.
#
# Background: ask-user-question.md "Parallel decision tracks must split into a questions array (HARD STOP)".
# failed-attempts.md tracks 3 recurrences (2026-05-04, 2026-05-16, 2026-05-28) plus a
# 4th action-axis (non-finding) sub-variant added 2026-07-25: a single option's
# description bundles 3+ independent fix actions while sibling option labels
# vary only by a scope word (all/except/only) — see ACTION_BUNDLE_TRIGGER below.
# Rule strengthening alone did not prevent recurrence; this hook automates the gate.

# Load locale-specific regex patterns from data/. The file is git-ignored so
# the public es6kr/skills repo never contains Korean characters. When the data
# file is missing (e.g., fresh clone in a non-Korean environment), each
# variable falls back to an English-only pattern via ${VAR:-default} below.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
HG_AXIS_TALLY_KO_SUFFIX="${HG_AXIS_TALLY_KO_SUFFIX:-}"
HG_AXIS_COUNT_TOKEN="${HG_AXIS_COUNT_TOKEN:-([2-9]|[1-9][0-9])[[:space:]]+(findings|issues|points|items)}"
HG_AXIS_DISPO_VERB="${HG_AXIS_DISPO_VERB:-dispose|include|post the}"
HG_AXIS_SCOPE_WORD="${HG_AXIS_SCOPE_WORD:-\\ball\\b|\\bexcept\\b|\\bexcluding\\b|\\bwithout\\b|\\bonly\\b|\\bpartial(ly)?\\b}"

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "AskUserQuestion" ]]; then
  exit 0
fi

# Get questions count
QCOUNT=$(echo "$INPUT" | jq -r '.tool_input.questions | length' 2>/dev/null)
if [[ -z "$QCOUNT" || "$QCOUNT" != "1" ]]; then
  # 0 questions = invalid input (let other validation handle); 2+ = axis already split (OK)
  exit 0
fi

# Collect axis-detection text: question text + option labels only.
# Description body is excluded — it often lists affected files / explanations
# for a SINGLE axis decision (e.g., "adopt this rule → PROMPT.md/fix_plan.md changes").
# False-positive case (2026-05-29): single-axis ask "adopt rule?" with 3 file
# paths in descriptions → previously triggered axis-merged DENY incorrectly.
OPT_TEXT=$(echo "$INPUT" | jq -r '
  .tool_input.questions[0] |
  (.question // ""),
  (.options[]? | .label // "")
' 2>/dev/null)

if [[ -z "$OPT_TEXT" ]]; then
  exit 0
fi

# Strip "keyword + count" summary forms (e.g., "Critical 0 / Important 2 /
# Minor 2", plus a locale counter suffix from data/hangul-patterns.regex
# HG_AXIS_TALLY_KO_SUFFIX) before keyword extraction — those are severity
# TALLIES describing one review result, not per-finding decision axes. A real
# multi-finding ask writes keywords without adjacent counts ("[#1 Refactor
# variables.tf] ..."). False-positive case: a verdict ask quoting
# "Critical 0 / Important 2 / Minor 2" → DENY incorrectly.
FINDING_TEXT=$(echo "$OPT_TEXT" | sed -E "s/(Refactor|Tip|Nitpick|Critical|Important|Minor)[[:space:]]*[0-9]+${HG_AXIS_TALLY_KO_SUFFIX}//gI")

# Detect finding-type keywords (case-insensitive, word-boundary-ish)
FINDING_KEYWORDS=$(echo "$FINDING_TEXT" | grep -oiE '\b(Refactor|Tip|Nitpick|Critical|Important|Minor)\b' | sort -u)
FINDING_COUNT=$(echo "$FINDING_KEYWORDS" | grep -c . 2>/dev/null || true)
FINDING_COUNT=${FINDING_COUNT:-0}

# Detect file:line identifiers (e.g., variables.tf:172, main.tf:14-27, inventory.yml:138)
# Aggregate union for the legacy single-signal heuristic.
PATH_LINE=$(echo "$OPT_TEXT" | grep -oE '[A-Za-z0-9_/.-]+\.(tf|tfvars|md|ya?ml|ts|tsx|js|jsx|py|go|rs|sh|sql|java|kt)(:[0-9]+(-[0-9]+)?)?' | sort -u)
PATH_COUNT=$(echo "$PATH_LINE" | grep -c . 2>/dev/null || true)
PATH_COUNT=${PATH_COUNT:-0}

# Per-option file analysis (FP refinement for "single axis option bundling multiple files").
# Failed-attempts pattern: a single option label like "Apply to skill.md and topic.md"
# bundles 2+ files for ONE bundled action, while other options have 0 files
# (e.g., "Defer"). The legacy union-count triggered DENY incorrectly.
#
# Correct multi-axis signal: each option points to DISTINCT files (disjoint sets).
# Single axis signals (skip path-count trigger):
#   - Only one option contains files; others empty → bundled action axis
#   - All file-bearing options share the same file set → same-target action axis
#   - File sets overlap (any pair) → same-target action axis with bundles
#   - Bare filenames (no :line) spread 1-per-option with zero finding keywords
#     → destination-choice single axis ("record this WHERE?" — each option IS a
#     candidate location, choose-one). Real per-file finding asks cite file:line
#     or carry finding-type keywords. (FP case: location-choice ask with
#     common/CLAUDE md candidates denied incorrectly.)
# Interpreter resolution: probe for a WORKING python, not merely a name on
# PATH. The Windows py3 shim is a Microsoft Store stub that exits 49 without
# running anything, so a name-only check leaves every python-backed check
# silently dead (stderr is discarded and the caller fails open).
# Fallback is the real `false` command, not an empty string — "$PY" -c '...'
# with PY="" invokes an empty command word, which still fails (and is still
# silenced by 2>/dev/null + the downstream :-0 defaults) but is an accidental
# empty-arg invocation rather than an intentional, self-documenting failure.
PY="false"
for _c in python3 python; do
  if command -v "$_c" >/dev/null 2>&1 && "$_c" -c "pass" >/dev/null 2>&1; then
    PY="$_c"; break
  fi
done

PATH_AXIS_MULTI=$(INPUT_JSON="$INPUT" "$PY" -c '
import json, re, os
try:
    data = json.loads(os.environ.get("INPUT_JSON", "{}"))
except Exception:
    print("0 0"); raise SystemExit(0)
opts = (data.get("tool_input", {}).get("questions", [{}])[0] or {}).get("options", []) or []
pat = re.compile(r"[A-Za-z0-9_/.-]+\.(?:tf|tfvars|md|ya?ml|ts|tsx|js|jsx|py|go|rs|sh|sql|java|kt)(?::[0-9]+(?:-[0-9]+)?)?")
per_option = []
has_line = 0
multi_file_option = 0
for o in opts:
    label = (o or {}).get("label", "") or ""
    files = set(pat.findall(label))
    if any(":" in f for f in files):
        has_line = 1
    if len(files) >= 2:
        multi_file_option = 1
    if files:
        per_option.append(files)
# Need at least 2 options with files to claim distinct-file multi-axis.
if len(per_option) < 2:
    print("0 0"); raise SystemExit(0)
# Multi-axis iff every pair of file-bearing options is disjoint.
for i in range(len(per_option)):
    for j in range(i+1, len(per_option)):
        if per_option[i] & per_option[j]:
            print("0 0"); raise SystemExit(0)
# Second flag: strong finding signal — any file:line identifier or an option
# bundling 2+ files. Bare 1-file-per-option alternatives look like a
# destination choice; the bash side requires finding keywords in that case.
print("1", 1 if (has_line or multi_file_option) else 0)
' 2>/dev/null)

# PATH_COUNT >= 2 is now refined: trigger only when per-option analysis confirms
# disjoint file sets across 2+ options. A single option bundling N files is
# single-axis (action on a bundle), not multi-axis. Disjoint bare filenames
# (no :line anywhere) with zero finding keywords = destination-choice single
# axis — skip the path trigger.
PATH_STRONG=${PATH_AXIS_MULTI#* }
PATH_AXIS_MULTI=${PATH_AXIS_MULTI%% *}
PATH_AXIS_MULTI=${PATH_AXIS_MULTI:-0}
PATH_STRONG=${PATH_STRONG:-0}
PATH_TRIGGER=0
if [[ "$PATH_COUNT" -ge 2 && "$PATH_AXIS_MULTI" == "1" ]]; then
  if [[ "$PATH_STRONG" == "1" || "$FINDING_COUNT" -ge 1 ]]; then
    PATH_TRIGGER=1
  fi
fi

# Variant: N-findings-disposed-in-one-question (count-token signal).
# Bypass case this covers: findings enumerated inside an option DESCRIPTION
# (descriptions are excluded from OPT_TEXT above) and named in a locale that
# keeps both keyword and file:line signals silent. The question text itself
# then carries a finding-count token, e.g. "Review complete (4 findings) —
# how to proceed?" — N>=2 findings being disposed through ONE question.
# Detection: QCOUNT==1 AND question text has finding-noun adjacent to a 2+
# count AND question/labels carry a disposition verb targeting the findings.
# Disposition-verb requirement keeps severity-tally verdict asks (e.g.
# "Critical 4 findings — ready to merge?") out of scope: hold/merge verbs are
# intentionally NOT in the disposition list.
# Locale variants (noun-count word order, additional disposition verbs) come
# from data/hangul-patterns.regex (HG_AXIS_COUNT_TOKEN, HG_AXIS_DISPO_VERB).
QTEXT=$(echo "$INPUT" | jq -r '.tool_input.questions[0].question // ""' 2>/dev/null)
COUNT_TOKEN=$(echo "$QTEXT" | grep -cE "$HG_AXIS_COUNT_TOKEN" 2>/dev/null || true)
COUNT_TOKEN=${COUNT_TOKEN:-0}
DISPO_VERB=$(printf '%s\n%s\n' "$QTEXT" "$OPT_TEXT" | grep -cE "$HG_AXIS_DISPO_VERB" 2>/dev/null || true)
DISPO_VERB=${DISPO_VERB:-0}
COUNT_TRIGGER=0
if [[ "$COUNT_TOKEN" -ge 1 && "$DISPO_VERB" -ge 1 ]]; then
  COUNT_TRIGGER=1
fi

# Variant: action-bundle-behind-disposition-scope (action-axis, non-finding;
# 2026-07-25). Bypass case this covers: the finding-keyword/file-path/count-
# token scans above all miss when a SINGLE option's DESCRIPTION bundles 3+
# independent fix actions (verb-led clauses) while sibling option LABELS vary
# only by a scope modifier ("Apply all fixes now" / "Apply fixes except X" /
# "Leave as report"). Description text is otherwise excluded from axis
# detection (see the OPT_TEXT comment above — FP guard for single-axis
# explanations); this variant re-admits description text ONLY when a scope
# word also appears in an option LABEL, since that combination is the actual
# signal ("same bundle, sliced by how much of it to apply"), not "one target,
# explained in detail". Requires >=2 options with files/verb-clauses is NOT
# needed here — a single option bundling 3+ actions is already the violation.
SCOPE_WORD_HIT=$(echo "$OPT_TEXT" | grep -ciE "$HG_AXIS_SCOPE_WORD" 2>/dev/null || true)
SCOPE_WORD_HIT=${SCOPE_WORD_HIT:-0}

ACTION_BUNDLE_TRIGGER=0
ACTION_BUNDLE_VERBS=""
if [[ "$SCOPE_WORD_HIT" -ge 1 ]]; then
  ACTION_BUNDLE_RESULT=$(INPUT_JSON="$INPUT" "$PY" -c '
import json, re, os
try:
    data = json.loads(os.environ.get("INPUT_JSON", "{}"))
except Exception:
    print("0"); raise SystemExit(0)
opts = (data.get("tool_input", {}).get("questions", [{}])[0] or {}).get("options", []) or []
VERBS = r"\b(sync|remove|add|normalize|clean up|edit|fix|update|register|apply|merge|drop|delete|create|write|implement|revert|keep)\b"
clause_re = re.compile(r",\s+|;\s+|\band\b|\n+\s*[-*•]?\s*", re.IGNORECASE)
verb_re = re.compile(VERBS, re.IGNORECASE)
for o in opts:
    desc = (o or {}).get("description", "") or ""
    clauses = [c for c in clause_re.split(desc) if c.strip()]
    verby = [c.strip()[:40] for c in clauses if verb_re.search(c)]
    if len(verby) >= 3:
        print("1|" + "; ".join(verby[:5]))
        raise SystemExit(0)
print("0")
' 2>/dev/null)
  ACTION_BUNDLE_RESULT=${ACTION_BUNDLE_RESULT:-0}
  if [[ "$ACTION_BUNDLE_RESULT" == 1\|* ]]; then
    ACTION_BUNDLE_TRIGGER=1
    ACTION_BUNDLE_VERBS="${ACTION_BUNDLE_RESULT#1|}"
  fi
fi

# Trigger if finding-type signal is 2+ OR per-option file analysis flags multi-axis
# OR the count-token variant fires OR the action-bundle-behind-scope variant fires
if [[ "$FINDING_COUNT" -ge 2 || "$PATH_TRIGGER" -eq 1 || "$COUNT_TRIGGER" -eq 1 || "$ACTION_BUNDLE_TRIGGER" -eq 1 ]]; then
  {
    echo "DENIED: AskUserQuestion has questions.length == 1 but options span multiple independent axes."
    echo ""
    echo "Detected axis signals:"
    if [[ "$FINDING_COUNT" -ge 2 ]]; then
      echo "  Finding-type keywords (${FINDING_COUNT} distinct):"
      echo "$FINDING_KEYWORDS" | sed 's/^/    - /'
    fi
    if [[ "$PATH_COUNT" -ge 2 ]]; then
      echo "  File/path identifiers (${PATH_COUNT} distinct):"
      echo "$PATH_LINE" | sed 's/^/    - /'
    fi
    if [[ "$COUNT_TRIGGER" -eq 1 ]]; then
      echo "  Finding-count token in question text (N findings disposed via ONE question):"
      echo "    - question: $QTEXT"
      echo "    - Required: one question PER finding (questions array), then a separate disposition ask"
    fi
    if [[ "$ACTION_BUNDLE_TRIGGER" -eq 1 ]]; then
      echo "  Action bundle behind a disposition-scope option (scope word + 3+ verb clauses in one option's description):"
      echo "    - clauses: $ACTION_BUNDLE_VERBS"
      echo "    - Required: one question PER independent fix/finding, ask disposition (apply/skip/hold) LAST or as a follow-up"
    fi
    echo ""
    echo "Why blocked:"
    echo "  - Each finding/file = independent decision axis (apply / register-separate / defer)"
    echo "  - Single question forces a single-choice selection, stripping user's per-axis decision authority"
    echo "  - failed-attempts.md 'axis-merged single-question' 3 recurrences (2026-05-04, 2026-05-16, 2026-05-28)"
    echo ""
    echo "Required: split into multiple questions in the questions array."
    echo ""
    echo "Correct pattern (example):"
    echo "  AskUserQuestion({"
    echo "    questions: ["
    echo "      { question: '[#1 Refactor variables.tf] how to handle?', options: [apply, register-separate, defer] },"
    echo "      { question: '[#2 Tip main.tf] how to handle?', options: [apply, defer] },"
    echo "      { question: '[#3 Nitpick inventory.yml] how to handle?', options: [apply, register-separate, defer] }"
    echo "    ]"
    echo "  })"
    echo ""
    echo "Reference: ask-user-question.md 'Parallel decision tracks must split into a questions array (HARD STOP)'"
  } >&2
  exit 2
fi

exit 0
