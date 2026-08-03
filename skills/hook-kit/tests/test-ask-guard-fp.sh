#!/usr/bin/env bash
# FP-regression tests for ask-guard.sh retrospective/deferred guards.
#
# Covers two false-positive classes that were over-blocking real sessions:
#   1. check_merge_without_review() flagging retrospective "post-merge" /
#      "validation" text (and the snake_case function name "check_merge_without_review"
#      itself) as an active merge proposal.
#   2. check_release_please_close() flagging deferred / negated close text
#      ("publish/close deferred", "cannot close ... without a merged PR") as an
#      active close proposal.
#
# Fixtures are English-only so the PUBLIC repo hangul-check never trips. The
# locale-specific equivalents (the discard-changes and merge-complete keywords)
# are exercised only through data/hangul-patterns.regex at runtime, not here.
#
# gh is neutralized via PATH so tests are deterministic/offline. FP cases return
# 0 before any gh lookup; TP cases block on missing attestation (gh-absent =
# allowlist skipped = fail-closed, the intended behavior).
#
# Run:  bash skills/hook-kit/tests/test-ask-guard-fp.sh
# Exit: 0 = all pass, 1 = any fail.

set -u
GUARD="$(cd "$(dirname "$0")/.." && pwd)/resources/ask-guard.sh"
[[ -f "$GUARD" ]] || { echo "guard not found: $GUARD" >&2; exit 1; }

TMPERR="$(mktemp)"
trap 'rm -f "$TMPERR"' EXIT
FAIL=0

# Build an AskUserQuestion payload from "label::description" option pairs.
mk() {
  local opts="" pair label desc
  for pair in "$@"; do
    label="${pair%%::*}"; desc="${pair#*::}"
    label=$(printf '%s' "$label" | sed 's/"/\\"/g')
    desc=$(printf '%s' "$desc" | sed 's/"/\\"/g')
    opts="${opts:+$opts,}{\"label\":\"$label\",\"description\":\"$desc\"}"
  done
  printf '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"options":[%s]}]}}' "$opts"
}
run() { printf '%s' "$1" | PATH="/nonexistent:$PATH" bash "$GUARD" >/dev/null 2>"$TMPERR"; echo $?; }
check() { # name want_rc got_rc
  local name="$1" want="$2" got="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS  $name (exit=$got)"
  else
    echo "FAIL  $name (exit=$got want=$want)"; echo "      stderr: $(head -1 "$TMPERR")"; FAIL=1
  fi
}

# ---- FP cases: must ALLOW (exit 0) ----

# 1. snake_case function name "_merge_" + retrospective post-merge verification.
check "fp1 fn-name + post-merge verify" 0 "$(run "$(mk \
  'Issue #36 hook allowlist::ask-guard.sh check_merge_without_review() adds release-please bot allowlist + 4 smoke tests' \
  'PR #51 post-merge Skill dispatch verification::Fresh session for dispatch behavior verification. No code change; validation only')")"

# 2. post-merge carryover follow-up work, not a merge proposal.
check "fp2 post-merge carryover" 0 "$(run "$(mk \
  'PR #47 post-merge follow-up::register fix-plan in release-please-config after merge. validation only, PR #47')")"

# 3. release-please + "publish/close deferred" — deferral, not close.
check "fp3 release-please close deferred" 0 "$(run "$(mk \
  'Implement allowlist now::add release-please allowlist to hook-kit. publish/close deferred to a separate decision (issue #36)')")"

# 4. release-please + "cannot close ... without a merged PR" — negated close.
check "fp4 release-please cannot close" 0 "$(run "$(mk \
  'Publish hook-kit first::register in release-please-config, then PR #36. cannot close the issue without a merged PR')")"

# 5. "merge --abort" — abort/cancel, never a merge proposal.
check "fp5 merge --abort" 0 "$(run "$(mk \
  'Abort and adopt main::merge --abort then adopt main b735f41 (drop a433db6). PR #79')")"

# 6. plain merge keyword only inside a retrospective validation line.
check "fp6 retrospective validation only" 0 "$(run "$(mk \
  'PR #63 post-merge validation::verification only, no code change. Squash type was already chosen')")"

# ---- TP cases: must BLOCK (exit 2) — attestation/verification genuinely absent ----

# 7. active "Squash and merge PR #N" without AI Review Summary attestation.
check "tp1 active merge no attestation" 2 "$(run "$(mk \
  'Squash and merge PR #34::merge the feature PR now')")"

# 8. active close of a release-please PR without verification attestation.
check "tp2 active release-please close no verify" 2 "$(run "$(mk \
  'Close release-please PR #55::close the release-please PR #55 directly, then re-cascade')")"

echo ""
if [[ "$FAIL" -eq 0 ]]; then echo "ALL PASS"; else echo "SOME FAILED"; fi
exit "$FAIL"
