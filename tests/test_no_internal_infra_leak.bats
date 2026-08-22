#!/usr/bin/env bats
# Guard: no denylisted internal values (hostnames, usernames) in PUBLIC skill content.
#
# Origin: a script hardcoded an internal service host and a personal Windows username
# path — flagged Important by Copilot on the next-fix->main promotion (PR #363).
#
# Because es6kr/skills is PUBLIC, this guard embeds NO specific internal value in tracked
# content. The forbidden ERE patterns live in a git-ignored local denylist
# (tests/.infra-denylist.local), present only on maintainer machines. Run this test from a
# local pre-commit / pre-push hook, or via `bats tests/` before pushing. In CI (no local
# denylist) the check is skipped (fail-open) — see .infra-denylist.local for the format.
#
# A generic regex was intentionally NOT used for these: this repo documents Windows path
# handling extensively (docstrings, tables, comments), so any generic drive-letter
# Users/<name> pattern false-positives on legitimate documentation. The denylist keeps
# the check precise and keeps the literal values out of the public repo.
#
# Scope: only git-tracked files under skills/ are scanned. This test lives in tests/,
# so it is never self-matched.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"

@test "no denylisted internal value in skill content (local denylist; fail-open in CI)" {
  local denylist="$REPO_ROOT/tests/.infra-denylist.local"
  if [[ ! -f "$denylist" ]]; then
    skip "no local denylist ($denylist present only on maintainer machines) — fail-open"
  fi
  local pat hits all=""
  while IFS= read -r pat || [[ -n "$pat" ]]; do
    [[ -z "$pat" || "$pat" == \#* ]] && continue
    hits=$(git -C "$REPO_ROOT" grep -nE "$pat" -- skills/ 2>/dev/null || true)
    [[ -n "$hits" ]] && all+="$hits"$'\n'
  done < "$denylist"
  [[ -z "$all" ]] || { echo "Denylisted internal value in skill content:"; echo "$all"; return 1; }
}
