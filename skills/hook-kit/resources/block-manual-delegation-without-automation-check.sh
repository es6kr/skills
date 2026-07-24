#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — block options that delegate manual work without
# evidence that available automation skills were considered.
#
# Rationale:
#   failed-attempts.md "manual delegation" pattern accumulated 6 occurrences
#   (2026-04-25 .. 2026-06-28) across 6 different domains (API research,
#   web automation, infra/SSH, WebFetch fallback, Syncthing conflict,
#   defined.net Console rename). Domain-specific rules failed to generalize.
#   Hook escalation step per failed-attempts.md "additional escalation
#   (6th occurrence — hook required)".
#
# Spec:
#   For each AskUserQuestion option (label + description):
#     - Detect manual-delegation keyword (Korean equivalents of "manual" /
#       "user does it directly" / manual / Console UI / browser to access /
#       paste-token / etc.)
#     - If detected, the option's description must include automation-skill
#       evidence (web-browser / Playwright / chrome-devtools / wmux +
#       a status word like unavailable/disconnected/tried/failed/expired) or
#       an explicit "no automation applicable" disclosure
#   On violation: emit a helpful guidance message + exit 2 (block).
#
# Self-test:
#   bash <this-script> --test
#   Runs 3 positive (block) + 8 negative (allow) fixtures, plus 5 more
#   Korean-language fixtures (2 positive, 3 negative) from a git-ignored data
#   file if present (data/manual-delegation-korean-fixtures.sh).

set -uo pipefail

# ----- Locale data (Korean keyword set) -----
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi

# Korean fallback is empty in non-Korean envs — only English patterns apply.
HG_MD_KEYWORDS_KO="${HG_MD_KEYWORDS_KO:-}"
HG_MD_HOLD_KEYWORDS_KO="${HG_MD_HOLD_KEYWORDS_KO:-}"
HG_MD_ASSISTANT_KO="${HG_MD_ASSISTANT_KO:-}"
HG_MD_USER_KO="${HG_MD_USER_KO:-}"

# English manual-delegation triggers. Matched case-insensitively (-i in the
# loop below), so no separate capitalized alternatives are needed here.
HG_MD_KEYWORDS_EN='\bmanual\b|Console UI|browser to access|user paste|user pastes|paste.*token|paste.*credential|copy.*from console|click.*dashboard|click.*console|browser to (click|navigate|fill)|user clicks'

# Automation-skill evidence — presence in the option description justifies the
# manual choice. Status word required to ensure the mention is a deliberation
# (not just a passing reference).
AUTOMATION_EVIDENCE='web-browser|Playwright|playwright|chrome-devtools|chrome devtools|wmux|cmux|browser automation|mcp__.*browser'
AUTOMATION_STATUS='unavailable|disconnected|tried|attempted|failed|expired|missing|not applicable|login wall|rate-limited|degraded'

# Combined evidence pattern — must mention an automation skill AND a status
EVIDENCE_PATTERN='(web-browser|Playwright|playwright|chrome-devtools|chrome devtools|wmux|cmux|browser automation|mcp__.*browser).*(unavailable|disconnected|tried|attempted|failed|expired|missing|not applicable|login wall|rate-limited|degraded)|(unavailable|disconnected|tried|attempted|failed|expired|missing|not applicable|login wall|rate-limited|degraded).*(web-browser|Playwright|playwright|chrome-devtools|chrome devtools|wmux|cmux|browser automation|mcp__.*browser)|no automation (applicable|available)|automation skill (unavailable|disconnected|missing)'

# Browser/token-context manual delegation additionally requires cmux/wmux probe
# evidence -- one disconnected MCP (chrome-devtools) is not proof that no
# automation exists while a managed-surface backend (cmux/wmux) may be present.
BROWSER_CTX="${HG_MD_BROWSER_CTX:-token|Token|PAT|sign-in|Console UI|dashboard|settings/tokens}"
CMUX_EVIDENCE='(cmux|wmux).{0,60}(unavailable|not installed|missing|absent|no surface|probed|checked|tried|attempted|failed)|(unavailable|not installed|missing|absent|no surface|probed|checked|tried|attempted|failed).{0,60}(cmux|wmux)'

# Build manual-delegation pattern, accommodating empty Korean fallback
if [[ -n "$HG_MD_KEYWORDS_KO" ]]; then
  MD_PATTERN="(${HG_MD_KEYWORDS_KO}|${HG_MD_KEYWORDS_EN})"
else
  MD_PATTERN="(${HG_MD_KEYWORDS_EN})"
fi

# ----- Self-test mode -----
if [[ "${1:-}" == "--test" ]]; then
  PASS=0
  FAIL=0
  FAILED_NAMES=()

  test_case() {
    local name="$1" expected="$2" input="$3"
    local actual
    set +e
    echo "$input" | "$0" >/dev/null 2>&1
    actual=$?
    set -e
    if [[ "$actual" == "$expected" ]]; then
      echo "  PASS: $name (exit=$actual)"
      PASS=$((PASS+1))
    else
      echo "  FAIL: $name (expected=$expected got=$actual)"
      FAIL=$((FAIL+1))
      FAILED_NAMES+=("$name")
    fi
  }

  set +e
  echo "=== Positive fixtures (should block, exit 2) ==="

  test_case "Manual fallback English without evidence" 2 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Manual fallback","description":"User pastes API token from dashboard"},{"label":"Skip","description":"skip for now"}]}]}}'

  test_case "browser to access dashboard" 2 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Dashboard","description":"Use browser to access settings page"},{"label":"skip","description":"skip"}]}]}}'

  test_case "Console UI click without evidence" 2 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Console","description":"Click through Console UI to grant permission"},{"label":"skip","description":"skip"}]}]}}'

  echo ""
  echo "=== Negative fixtures (should allow, exit 0) ==="

  test_case "No manual keyword in any option" 0 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Proceed","description":"automation via REST API"},{"label":"Hold","description":"defer until later"}]}]}}'

  test_case "Manual + Playwright login wall" 0 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Manual","description":"Playwright tried but login wall hit, manual fallback"},{"label":"skip","description":"skip"}]}]}}'

  # Korean-language fixtures (5 cases: 2 positive, 3 negative) live in a
  # git-ignored data file so the public repo stays zero-Korean -- same
  # pattern as data/hangul-patterns.regex. Skipped gracefully if absent.
  HG_MD_TEST_FIXTURES="$(dirname "$0")/../data/manual-delegation-korean-fixtures.sh"
  if [[ -f "$HG_MD_TEST_FIXTURES" ]]; then
    # shellcheck source=/dev/null
    . "$HG_MD_TEST_FIXTURES"
    run_korean_fixtures
  else
    echo "  (skipped: Korean-language fixtures data file not present)"
  fi

  # Regression: EVIDENCE_PATTERN case-sensitivity (found in this session — a
  # capitalized "No automation applicable" evidence phrase was silently
  # rejected by a lowercase-only grep, blocking a legitimate non-manual option).
  test_case "Manual option with capitalized 'No automation applicable'" 0 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Manual","description":"No automation applicable — chrome-devtools disconnected"},{"label":"skip","description":"skip"}]}]}}'

  # Regression: negation-lookback (found in this session — an automated
  # option's description containing "no second manual trigger needed" was
  # flagged as manual-delegation purely on the bare word "manual", with no
  # automation-skill evidence to satisfy the check since the option describes
  # automation, not delegation).
  test_case "Automated option describing absence of manual re-trigger" 0 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Scripted integration test","description":"Real install against the marketplace, asserts activation completes within one call, no second manual trigger needed"},{"label":"skip","description":"skip"}]}]}}'

  # Regression: BROWSER_CTX must stay case-sensitive. "PAT" (bare, no word
  # boundary) case-insensitively matches "pat" inside ordinary words like
  # "path" -- found while fixing the two bugs above, when a manual+evidence
  # fixture whose description happened to end in "...only path" started
  # false-triggering the cmux-probe gate. (Korean-language variant of this
  # same regression lives in the data-file fixtures below.)
  test_case "Manual + evidence, description contains the word path (not PAT)" 0 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Manual fallback","description":"web-browser MCP unavailable, manual fallback only path"},{"label":"skip","description":"skip"}]}]}}'

  test_case "Token-context manual without cmux probe (cmux gate)" 2 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Manual","description":"User pastes token from settings/tokens page - chrome-devtools disconnected, no other automation applicable"},{"label":"skip","description":"skip"}]}]}}'

  test_case "Token-context manual with cmux probe evidence" 0 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Manual","description":"User pastes token - chrome-devtools disconnected and cmux not installed, manual only path"},{"label":"skip","description":"skip"}]}]}}'

  test_case "Self-name quotation" 0 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Review","description":"Discuss block-manual-delegation hook rules"},{"label":"skip","description":"skip"}]}]}}'

  test_case "Domain-terminology manual sync near ArgoCD" 0 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Sync","description":"Trigger ArgoCD manual sync for deployment"},{"label":"skip","description":"skip"}]}]}}'

  test_case "Domain-terminology manual sync without context" 2 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Sync","description":"Trigger manual sync for deployment"},{"label":"skip","description":"skip"}]}]}}'

  test_case "Hold option deferring manual task" 0 '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Hold","description":"Defer manual token generation and record to fix_plan"},{"label":"skip","description":"skip"}]}]}}'

  set -e
  echo ""
  echo "Total: $((PASS+FAIL)), Pass: $PASS, Fail: $FAIL"
  if [[ $FAIL -gt 0 ]]; then
    echo "Failed cases:"
    for n in "${FAILED_NAMES[@]}"; do
      echo "  - $n"
    done
    exit 1
  fi
  exit 0
fi

# ----- Normal hook flow -----
INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" != "AskUserQuestion" ]] && exit 0

# Emit each option as "label\tdescription" lines
HITS=$(echo "$INPUT" | jq -r '
  .tool_input.questions[]? | .options[]? |
  (.label // "") + "\t" + (.description // "")
' 2>/dev/null)

[[ -z "$HITS" ]] && exit 0

VIOLATIONS=()
CMUX_VIOLATIONS=()
while IFS=$'\t' read -r label desc; do
  [[ -z "$label" && -z "$desc" ]] && continue
  combined="${label} ${desc}"

  # 1. Self-name quotation exception
  if echo "$combined" | grep -qEi "block-manual-delegation"; then
    continue
  fi

  # 2. Domain-terminology close proximity exception (ArgoCD/GitOps/k8s/Terraform/PAM)
  if echo "$combined" | grep -qEi "(manual (sync|apply|deploy|trigger|promotion)|non-automated).{0,40}(ArgoCD|GitOps|k8s|kubernetes|Terraform|PAM|argocd)" \
     || echo "$combined" | grep -qEi "(ArgoCD|GitOps|k8s|kubernetes|Terraform|PAM|argocd).{0,40}(manual (sync|apply|deploy|trigger|promotion)|non-automated)"; then
    continue
  fi

  # 3. Hold/carryover-only exception
  hold_pattern='\b(hold|defer|carryover|postpone)\b'
  if [[ -n "$HG_MD_HOLD_KEYWORDS_KO" ]]; then
    hold_pattern="(${hold_pattern}|${HG_MD_HOLD_KEYWORDS_KO})"
  fi

  if echo "$combined" | grep -qEi "$hold_pattern"; then
    assistant_pattern='(I will|assistant|we will)'
    if [[ -n "$HG_MD_ASSISTANT_KO" ]]; then
      assistant_pattern="(${assistant_pattern}|${HG_MD_ASSISTANT_KO})"
    fi

    user_pattern='\b(you|user)\b'
    if [[ -n "$HG_MD_USER_KO" ]]; then
      user_pattern="(${user_pattern}|${HG_MD_USER_KO})"
    fi

    # Allow if assistant is the active subject or if there are no active user-directed nouns/verbs
    if echo "$desc" | grep -qEi "$assistant_pattern" \
       || ! echo "$desc" | grep -qEi "$user_pattern"; then
      continue
    fi
  fi

  # Negation-lookback: strip "no/not/without/zero ... manual" phrasing before
  # the delegation-keyword check, so an option describing the ABSENCE of
  # manual work (e.g. "no second manual trigger needed") doesn't false-positive
  # on the bare word "manual". Only affects this one check's input, not the
  # evidence checks below (which operate on the untouched $desc/$combined).
  # NOTE: \b is unreliable in BSD sed (macOS) in this position -- confirmed by
  # direct testing, not assumed. The (^|[^a-zA-Z]) / \1 capture-and-preserve
  # idiom is the portable substitute: it requires the negation word to start
  # at a non-letter boundary (or string start) without relying on \b at all.
  md_check_text=$(echo "$combined" | grep -qEi "$MD_PATTERN" \
    && echo "$combined" | sed -E 's/(^|[^a-zA-Z])(no|not|without|zero)[a-zA-Z ]{0,20}manual/\1/gi' \
    || echo "$combined")
  # Check manual-delegation keyword present (case-insensitive)
  # Self-name quotation exception (Issue #109): If option mentions the script name itself, skip
  if echo "$combined" | grep -qiE "block-manual-delegation"; then
    continue
  fi

  # Hold/carryover-only exception (Issue #109): If option is a pure hold/defer action assigned to assistant
  local hold_pattern="^(Hold|Defer|Carryover${HG_MD_HOLD_KEYWORDS_KO:+|$HG_MD_HOLD_KEYWORDS_KO})$"
  local user_pattern="user|human${HG_MD_USER_KO:+|$HG_MD_USER_KO}"
  if echo "$label" | grep -qiE "$hold_pattern"; then
    if ! echo "$desc" | grep -qiE "$user_pattern"; then
      continue
    fi
  fi

  # Domain-terminology exception (Issue #109): Infra/tool terms like "manual sync", "manual apply", "non-automated" near GitOps/k8s/ArgoCD
  if echo "$combined" | grep -qiE "(manual sync|manual apply|non-automated)" && \
     echo "$combined" | grep -qiE "(ArgoCD|argocd|gitops|k8s|kubernetes|root app)"; then
    continue
  fi

  if echo "$md_check_text" | grep -qEi "$MD_PATTERN"; then
    # Check automation evidence in description (case-insensitive)
    if ! echo "$desc" | grep -qEi "$EVIDENCE_PATTERN"; then
      VIOLATIONS+=("$label || $desc")
    # BROWSER_CTX/CMUX_EVIDENCE stay case-sensitive: BROWSER_CTX's bare "PAT"
    # alternative has no word boundary, and case-insensitive matching makes it
    # match "pat" inside ordinary words like "path" -- a real false positive
    # found while fixing the two case-sensitivity bugs above.
    elif echo "$combined" | grep -qE "$BROWSER_CTX" && ! echo "$desc" | grep -qE "$CMUX_EVIDENCE"; then
      CMUX_VIOLATIONS+=("$label || $desc")
    fi
  fi
done <<< "$HITS"

if [[ ${#VIOLATIONS[@]} -gt 0 ]]; then
  printf 'DENIED: AskUserQuestion option(s) delegate manual work without automation-skill check.\n\n' >&2
  printf 'Why blocked:\n' >&2
  printf '  - failed-attempts.md "manual delegation" 7 cumulative occurrences\n' >&2
  printf '    (2026-04-25 API / 2026-06-09 web-automation / 2026-06-19 infra /\n' >&2
  printf '     2026-06-24 WebFetch / 2026-06-27 Syncthing / 2026-06-28 Console /\n' >&2
  printf '     2026-07-06 cmux surface ignored on PAT issuance)\n' >&2
  printf '  - Manual-delegation keyword detected in option (label or description)\n' >&2
  printf '  - Option description does NOT mention checking automation skills first\n\n' >&2
  printf 'Violating options:\n' >&2
  for v in "${VIOLATIONS[@]}"; do
    printf '  - %s\n' "$v" >&2
  done
  printf '\nRequired action — include evidence in the offending option description:\n' >&2
  printf '  Pattern: <automation-skill> <status-word>\n' >&2
  printf '  Examples:\n' >&2
  printf '    "web-browser MCP unavailable, manual fallback"\n' >&2
  printf '    "Playwright tried, login wall hit"\n' >&2
  printf '    "chrome-devtools disconnected, no other automation applicable"\n' >&2
  printf '    "no automation applicable — token must come from email"\n\n' >&2
  printf 'Reference: ask-user-question.md "manual external work option directly\n' >&2
  printf 'before listing: grep available automation skills" guard\n' >&2
  exit 2
fi

if [[ ${#CMUX_VIOLATIONS[@]} -gt 0 ]]; then
  printf 'DENIED: browser/token-context manual delegation without cmux/wmux probe evidence.\n\n' >&2
  printf 'Why blocked:\n' >&2
  printf '  - Option delegates browser/token work to the user\n' >&2
  printf '  - Evidence cites another backend (e.g. chrome-devtools) but not the\n' >&2
  printf '    managed-surface backend (cmux/wmux) state\n' >&2
  printf '  - 7th manual-delegation occurrence: open <url> printed a cmux\n' >&2
  printf '    surface handle, yet token generation was delegated to the user\n\n' >&2
  printf 'Violating options:\n' >&2
  for v in "${CMUX_VIOLATIONS[@]}"; do
    printf '  - %s\n' "$v" >&2
  done
  printf '\nRequired action:\n' >&2
  printf '  1. Probe: command -v cmux / command -v wmux, and inspect the open\n' >&2
  printf '     output for a "surface=" handle (cmux-managed browser)\n' >&2
  printf '  2. If present, drive the page: cmux browser --surface <handle>\n' >&2
  printf '     snapshot|fill|click|eval -- do not delegate to the user\n' >&2
  printf '  3. Only if absent, add evidence like "cmux not installed" to the option\n\n' >&2
  printf 'Reference: web-browser/credential-issue.md "Managed-surface detection"\n' >&2
  exit 2
fi

exit 0
