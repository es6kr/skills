#!/usr/bin/env bats
# Behavioral tests for block-summary-fabricated-claims.sh (consolidate fabrication gate).
# Runs offline: cwd is a non-git tmpdir so the guard's local `git cat-file` short-circuit
# is inert, and a mock `gh` on PATH fully controls SHA existence + Copilot count lookups.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/consolidate/resources/block-summary-fabricated-claims.sh"

setup() {
  TESTDIR="$BATS_TEST_TMPDIR/work"
  MOCKBIN="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$TESTDIR" "$MOCKBIN"

  # Unset git environment variables so pre-push hook execution doesn't leak repo context into tmpdir
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_PREFIX

  # mock gh: real SHA => echoes .sha (rc 0); fake SHA (4e7ee9e / fake* / deadbee*) => 404-style err (rc 1);
  # pulls/*/comments => MOCK_COPILOT_COUNT (default 2)
  cat > "$MOCKBIN/gh" <<'MOCK'
#!/usr/bin/env bash
if [[ "$1" == "api" ]]; then
  path="$2"
  case "$path" in
    */commits/*)
      sha="${path##*/commits/}"
      if [[ "$sha" == 4e7ee9e* || "$sha" == fake* || "$sha" == deadbee* ]]; then
        echo "gh: No commit found for SHA: $sha (HTTP 422)" >&2
        exit 1
      fi
      echo "$sha"; exit 0 ;;
    */pulls/*/comments)
      echo "${MOCK_COPILOT_COUNT:-2}"; exit 0 ;;
  esac
fi
exit 0
MOCK
  chmod +x "$MOCKBIN/gh"
  PATH="$MOCKBIN:$PATH"
}

# build a consolidate-provenance body file and echo the command that posts it
_post_cmd() {
  local body_file="$TESTDIR/body.md"
  printf '%s\n' "$1" > "$body_file"
  echo "gh pr comment 346 -R es6kr/skills --body-file $body_file"
}

_run_guard() {
  cd "$TESTDIR"
  local cmd="$1"
  run bash "$GUARD" <<EOF
{"tool_name":"Bash","tool_input":{"command":$(printf '%s' "$cmd" | jq -Rs .)}}
EOF
}

@test "guard script exists and is executable" {
  [[ -x "$GUARD" ]]
}

@test "fabricated SHA (4e7ee9e) in a Summary is blocked" {
  local body="## AI Review Summary — [receiving-code-review](x)
<!-- consolidate:verified -->
| 9 | Internal | hooks.json | Fixed (commit 0d9b701, 035a27c, 4e7ee9e) | repaired |"
  _run_guard "$(_post_cmd "$body")"
  [[ "$status" -eq 2 ]]
  [[ "$output" == *"4e7ee9e"* ]]
}

@test "all-real SHAs in a Summary pass" {
  local body="## AI Review Summary — [receiving-code-review](x)
<!-- consolidate:verified -->
| 1 | copilot | Fixed (commit 055c8a2, 0d9b701) | ok |"
  _run_guard "$(_post_cmd "$body")"
  [[ "$status" -eq 0 ]]
}

@test "inflated Copilot count (claims 4, actual 2) is blocked" {
  MOCK_COPILOT_COUNT=2
  local body="## AI Review Summary — [receiving-code-review](x)
<!-- consolidate:verified -->
| GitHub Copilot | External | Completed | 4 findings (2 inline, 2 doc) |"
  _run_guard "$(_post_cmd "$body")"
  [[ "$status" -eq 2 ]]
  [[ "$output" == *"Copilot"* ]]
}

@test "correct Copilot count (claims 2, actual 2) passes" {
  MOCK_COPILOT_COUNT=2
  local body="## AI Review Summary — [receiving-code-review](x)
<!-- consolidate:verified -->
| GitHub Copilot | External | Completed | 2 findings (2 actionable inline) |"
  _run_guard "$(_post_cmd "$body")"
  [[ "$status" -eq 0 ]]
}

@test "non-consolidate review comment (no provenance) is not guarded" {
  local body="## CodeRabbit findings
one finding — will fix in commit 4e7ee9e"
  _run_guard "$(_post_cmd "$body")"
  [[ "$status" -eq 0 ]]
}

@test "override ALLOW_SUMMARY_FABRICATED_CLAIMS=1 bypasses the block" {
  local body="## AI Review Summary — [receiving-code-review](x)
<!-- consolidate:verified -->
Fixed (commit 4e7ee9e)"
  local bf="$TESTDIR/body.md"; printf '%s\n' "$body" > "$bf"
  _run_guard "ALLOW_SUMMARY_FABRICATED_CLAIMS=1 gh pr comment 346 -R es6kr/skills --body-file $bf"
  [[ "$status" -eq 0 ]]
}

@test "non-Bash tool call is ignored" {
  cd "$TESTDIR"
  run bash "$GUARD" <<'EOF'
{"tool_name":"Read","tool_input":{"file_path":"/tmp/x"}}
EOF
  [[ "$status" -eq 0 ]]
}

@test "a non-POST bash command is ignored even with a fabricated SHA in it" {
  _run_guard "echo commit 4e7ee9e receiving-code-review"
  [[ "$status" -eq 0 ]]
}
