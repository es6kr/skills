#!/usr/bin/env bash
# Regression tests for block-axis-merged-ask.sh, focused on the
# action-bundle-behind-disposition-scope heuristic (added 2026-07-25) that
# had zero dedicated fixture coverage (PR #195 deferred finding #36).
#
# Also covers a couple of the other documented variants (finding-keyword
# tally, per-option file bundling) as basic sanity/regression checks, since
# none of them had a test file either.
#
# Run:  bash skills/hook-kit/tests/test-block-axis-merged-ask.sh
# Exit: 0 = all pass, 1 = any fail.

set -u
GUARD="$(cd "$(dirname "$0")/.." && pwd)/resources/block-axis-merged-ask.sh"
[[ -f "$GUARD" ]] || { echo "guard not found: $GUARD" >&2; exit 1; }

TMPERR="$(mktemp)"
trap 'rm -f "$TMPERR"' EXIT
FAIL=0

# Build a single-question AskUserQuestion payload from "label::description" option pairs.
mk() {
  local q="$1"; shift
  local opts="" pair label desc
  for pair in "$@"; do
    label="${pair%%::*}"; desc="${pair#*::}"
    label=$(printf '%s' "$label" | sed 's/"/\\"/g')
    desc=$(printf '%s' "$desc" | sed 's/"/\\"/g')
    opts="${opts:+$opts,}{\"label\":\"$label\",\"description\":\"$desc\"}"
  done
  printf '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"%s","options":[%s]}]}}' "$q" "$opts"
}
run() { printf '%s' "$1" | bash "$GUARD" >/dev/null 2>"$TMPERR"; echo $?; }
check() { # name want_rc got_rc
  local name="$1" want="$2" got="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS  $name (exit=$got)"
  else
    echo "FAIL  $name (exit=$got want=$want)"; echo "      stderr: $(head -1 "$TMPERR")"; FAIL=1
  fi
}

# ---- Action-bundle-behind-scope heuristic (TP: must DENY, exit 2) ----

# 1. Single option's description bundles 3+ verb clauses, sibling labels vary
# only by a scope word ("all" / "except").
check "ab-tp1 scope-word + 3 verb clauses" 2 "$(run "$(mk \
  'How should I apply the review findings?' \
  'Apply all fixes now::sync the docs, remove the stale hook, add the missing test' \
  'Leave as report::no code changes this pass')")"

# 2. Same bundle pattern using "except" as the scope word.
check "ab-tp2 except scope-word" 2 "$(run "$(mk \
  'Apply findings?' \
  'Apply fixes except the flaky one::update the config, fix the typo, register the follow-up issue' \
  'Apply nothing::hold everything for next session')")"

# ---- Action-bundle heuristic (FP: must ALLOW, exit 0) ----

# 3. Scope word present but fewer than 3 verb clauses in the description.
check "ab-fp1 scope-word but only 2 verb clauses" 0 "$(run "$(mk \
  'Land the PR?' \
  'Merge all commits now::squash and push' \
  'Hold::wait for review')")"

# 4. 3+ verb-like words present but no scope word in any option label/description.
check "ab-fp2 verbs present, no scope word" 0 "$(run "$(mk \
  'What next?' \
  'Continue::sync the docs, remove the stale hook, add the missing test' \
  'Stop::end the session here')")"

# ---- Other variants: basic regression (already-covered heuristics, no prior test file) ----

# 5. Finding-type keyword tally (2+ distinct) → DENY.
check "kw-tp1 Critical + Minor distinct keywords" 2 "$(run "$(mk \
  'How to handle these findings?' \
  '[#1 Critical auth.ts] fix now::apply the patch' \
  '[#2 Minor lint.ts] fix now::apply the patch')")"

# 6. Severity TALLY (counts, not per-finding decisions) → ALLOW.
check "kw-fp1 severity tally, not per-finding" 0 "$(run "$(mk \
  'Ready to merge? Critical 0 / Important 2 / Minor 2' \
  'Merge now::all counts acceptable' \
  'Hold::review Important items first')")"

# 7. Single option bundling 2 distinct files for ONE action (single axis) → ALLOW.
check "path-fp1 single option bundles 2 files" 0 "$(run "$(mk \
  'Apply this fix?' \
  'Apply to skill.md and topic.md::update both docs together' \
  'Defer::not now')")"

# 8. Finding count with Korean counter suffix ("Finding 3" + counter) → ALLOW.
check "kw-fp2 Korean finding tally" 0 "$(run "$(mk \
  "$(printf 'Finding 3\uac74 \uac80\ud1a0 \uc644\ub8cc \u2014 \ub2e4\uc74c \uc9c4\ud589?')" \
  "$(printf '\ubc18\uc601::\ud328\uce58 \uc801\uc6a9')" \
  "$(printf '\ubcf4\ub958::\ub2e4\uc74c\uc5d0')")")"

# 9. Korean severity tally ("Critical 0 / Important 2 / Minor 2" + counter) → ALLOW.
check "kw-fp3 Korean severity tally with counter" 0 "$(run "$(mk \
  "$(printf '\uba38\uc9c0 \uc900\ube44 \uc644\ub8cc: Critical 0\uac74 / Important 2\uac74 / Minor 2\uac74')" \
  "$(printf '\uba38\uc9c0 \uc9c4\ud589::\ubaa8\ub4e0 \uc218\uce58 \uc9a9\uc871')" \
  "$(printf '\ubcf4\ub958::\uc7ac\uac80\ud1a0')")")"

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "ALL PASS"
else
  echo "SOME FAILED"
fi
exit "$FAIL"
