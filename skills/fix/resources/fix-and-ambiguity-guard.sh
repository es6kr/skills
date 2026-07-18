#!/usr/bin/env bash
# fix-and-ambiguity-guard.sh
# UserPromptSubmit hook: inject guards when the user prompt triggers /fix or contains ambiguous verb patterns.
# Source: failed-attempts.md recurrence patterns "root cause asserted from user statement alone" + "ambiguous-verb answer".

set -euo pipefail

INPUT="$(cat)"
PROMPT="$(echo "$INPUT" | python3 -c "import sys, json; d = json.load(sys.stdin); print(d.get('prompt', ''))" 2>/dev/null || echo "")"

[[ -z "$PROMPT" ]] && exit 0

# Locale detection patterns live in git-ignored data/ (Korean + English). The hook
# carries English-only fallbacks so the PUBLIC copy works without the data file.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
[ -f "$HG_DATA_FILE" ] && . "$HG_DATA_FILE"
FIX_AMBIGUITY_OPTION_VERB="${FIX_AMBIGUITY_OPTION_VERB:-(handle|process|deal[[:space:]]with|block|hold|defer|address)[[:space:]]+([0-9]+,[0-9]+(,[0-9]+)*|option[[:space:]]*[0-9]+|item[[:space:]]*[0-9]+)}"
FIX_CLAIM_PHRASING="${FIX_CLAIM_PHRASING:-(did[[:space:]]?n.?t|does[[:space:]]?n.?t|not)[[:space:]]+work|is[[:space:]]?n.?t[[:space:]]+working|why[[:space:]]+(not|again|keep|do you|did)}"

WARN=""

# 1. fix-trigger detection (/fix, fix: prefix)
if echo "$PROMPT" | grep -qiE "^(fix:|/fix( |\$|\b))"; then
  WARN+="
[FIX_GUARD] /fix or fix: prefix detected. Apply BEFORE Step 1 root-cause analysis:

- Do not assert a root cause from the user statement alone -> verify with primary sources (code, API responses, 5+ other samples)
- If the target the user refers to could be multiple things, use AskUserQuestion first (ask-user-question.md 'when multiple interpretations are possible, AskUserQuestion immediately')
- When adding a new detection criterion, a false-positive test against 5+ normal samples is mandatory
- Do not stop at Why 3 -> continue to Why 4 ('why was the existing rule not followed') and Why 5 ('where does that defect originate')
- Do not duplicate general behavior rules into fix.md -> those rules are already always_on in ask-user-question.md/common.md
- Pattern where prior fixes fell into the same trap: failed-attempts.md 'defended user suspicion with indirect evidence (2026-04-24)' / 'root cause asserted from user statement alone (2026-05-04)'
"
fi

# 2. Ambiguous verb + option number pattern (e.g. "handle 2,3", "option 2 hold")
# Only multi-comma numbers or "option N" form to avoid false positive on "tidy issue #100"
if echo "$PROMPT" | grep -qiE "$FIX_AMBIGUITY_OPTION_VERB"; then
  WARN+="
[AMBIGUITY_GUARD] 'option number + ambiguous verb' pattern detected.

- Ambiguous verbs are polysemous: 'handle' = (mark BLOCKED / hold / do the work / block, etc.)
- Do not act immediately; AskUserQuestion with a concrete verb per item is mandatory
- See failed-attempts.md 'ambiguous-verb answer, 4th recurrence (2026-05-04)'
- Follow the ask-user-question.md 'ambiguous verb pattern' table + 3-step self-check
"
fi

# 3. User-claim phrasing without source verification (e.g. "X didn't work", "why isn't X working")
if echo "$PROMPT" | grep -qiE "$FIX_CLAIM_PHRASING"; then
  WARN+="
[CLAIM_VERIFY_GUARD] user assertion phrasing detected.

- If the target the statement refers to is not specified, do not guess
- Reach a conclusion only after verifying with primary sources (gh pr view, Read, Grep)
- See failed-attempts.md 'defended user suspicion with indirect evidence (2026-04-24)' / 'root cause asserted from user statement alone (2026-05-04)'
- Apply common.md 'cross-verify state from multiple sources'
"
fi

if [[ -n "$WARN" ]]; then
  cat <<EOF
{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": $(printf '%s' "$WARN" | python3 -c 'import sys, json; print(json.dumps(sys.stdin.read()))')}}
EOF
fi

exit 0
