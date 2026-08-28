#!/usr/bin/env bash
# Smoke tests for the release-please bot-PR allowlist in ask-guard.sh
# (check_merge_without_review). Covers issue #36 acceptance criteria.
#
# gh is mocked via a PATH shim so the tests are deterministic and offline.
# Run:  bash skills/hook-kit/tests/test-ask-guard-allowlist.sh
# Exit: 0 = all pass, 1 = any fail.

set -u
GUARD="$(cd "$(dirname "$0")/.." && pwd)/resources/ask-guard.sh"
[[ -f "$GUARD" ]] || { echo "guard not found: $GUARD" >&2; exit 1; }

TESTDIR="$(mktemp -d)"
trap 'rm -rf "$TESTDIR" "$TESTDIR.out" "$TESTDIR.err"' EXIT

# --- mock gh -------------------------------------------------------------
# PR fixtures:
#   27  release-please[bot]  release-please--branches--main   (author + branch)
#   28  app/github-actions   some-other-branch                (author clause only)
#   34  someuser             feat/foo                         (regular feature PR)
#   999 (lookup failure — exit 1, empty output)
cat > "$TESTDIR/gh" <<'MOCK'
#!/usr/bin/env bash
if [[ "$1" == "repo" && "$2" == "view" ]]; then echo "es6kr/skills"; exit 0; fi
if [[ "$1" == "pr" && "$2" == "view" ]]; then
  case "$3" in
    27)  echo -e "release-please[bot]\trelease-please--branches--main"; exit 0 ;;
    28)  echo -e "app/github-actions\tsome-other-branch"; exit 0 ;;
    34)  echo -e "someuser\tfeat/foo"; exit 0 ;;
    999) exit 1 ;;
    *)   exit 1 ;;
  esac
fi
exit 0
MOCK
chmod +x "$TESTDIR/gh"

FAIL=0
mk() { # $1 = space-joined PR tokens like "#27" or "#27 #34"
  local opts="" tok
  for tok in $1; do
    opts="${opts:+$opts,}{\"label\":\"Squash and merge PR $tok\",\"description\":\"\"}"
  done
  echo "{\"tool_name\":\"AskUserQuestion\",\"tool_input\":{\"questions\":[{\"options\":[$opts]}]}}"
}
run() { echo "$1" | PATH="$TESTDIR:$PATH" bash "$GUARD" >"$TESTDIR.out" 2>"$TESTDIR.err"; echo $?; }
check() { # $1=name $2=expected_rc $3=expect_stderr(0|1)
  local name="$1" want_rc="$2" want_err="$3" got_rc="$4"
  local has_err=0; [[ -s "$TESTDIR.err" ]] && has_err=1
  if [[ "$got_rc" == "$want_rc" && "$has_err" == "$want_err" ]]; then
    echo "PASS  $name (exit=$got_rc, stderr=$has_err)"
  else
    echo "FAIL  $name (exit=$got_rc want=$want_rc, stderr=$has_err want=$want_err)"; FAIL=1
  fi
}

# (a) release-please PR only            -> allow (exit 0, no stderr)
check "a release-please only"      0 0 "$(run "$(mk '#27')")"
# (a2) two bot PRs                      -> allow
check "a2 two bot PRs"             0 0 "$(run "$(mk '#27 #27')")"
# (e) app/github-actions author,        -> allow via author clause (non-rp branch)
check "e author-clause only"       0 0 "$(run "$(mk '#28')")"
# (b) feature PR only, no attestation   -> deny (exit 2, stderr)
check "b feature no attestation"   2 1 "$(run "$(mk '#34')")"
# (c) mixed bot + feature               -> deny (feature still needs attestation)
check "c mixed bot+feature"        2 1 "$(run "$(mk '#27 #34')")"
# (d) lookup failure (404)              -> deny (fail closed)
check "d lookup failure"           2 1 "$(run "$(mk '#999')")"

echo ""
if [[ "$FAIL" -eq 0 ]]; then echo "ALL PASS"; else echo "SOME FAILED"; fi
exit "$FAIL"
