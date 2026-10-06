#!/usr/bin/env bats
# Behavioral tests for block-review-post-without-receiving-code-review.sh.
# Verifies the guard checks the session TRANSCRIPT for an actual
# Skill("superpowers:receiving-code-review") invocation, not just whether the
# posted body happens to contain that link text as a template string.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/consolidate/resources/block-review-post-without-receiving-code-review.sh"

setup() {
  TESTDIR="$BATS_TEST_TMPDIR/work"
  mkdir -p "$TESTDIR"
}

_review_body() {
  # A review-flavored body: mentions a review tool + a findings/severity cluster.
  printf '## AI Review Summary — [receiving-code-review](https://skills.sh/obra/superpowers/receiving-code-review)\n\nCodeRabbit review findings: 2 Major, 3 Minor. Verified against the diff.\n'
}

_make_transcript_with_skill() {
  local path="$TESTDIR/transcript_with_skill.jsonl"
  printf '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"superpowers:receiving-code-review"}}]}}\n' > "$path"
  echo "$path"
}

_make_transcript_without_skill() {
  local path="$TESTDIR/transcript_without_skill.jsonl"
  printf '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"echo hi"}}]}}\n' > "$path"
  echo "$path"
}

_run_guard() {
  local cmd="$1" transcript="$2"
  cd "$TESTDIR"
  run bash "$GUARD" <<EOF
{"tool_name":"Bash","tool_input":{"command":$(printf '%s' "$cmd" | jq -Rs .)},"transcript_path":$(printf '%s' "$transcript" | jq -Rs .)}
EOF
}

@test "guard script exists and is executable" {
  [[ -x "$GUARD" ]]
}

@test "review-flavored POST without receiving-code-review in transcript is DENIED" {
  local body_file="$TESTDIR/body.md"
  _review_body > "$body_file"
  local transcript
  transcript="$(_make_transcript_without_skill)"
  _run_guard "gh pr comment 600 -R es6kr/skills --body-file $body_file" "$transcript"
  [ "$status" -eq 2 ]
  [[ "$output" == *"DENIED"* ]]
  [[ "$output" == *"receiving-code-review"* ]]
}

@test "review-flavored POST with receiving-code-review actually invoked in transcript PASSES" {
  local body_file="$TESTDIR/body.md"
  _review_body > "$body_file"
  local transcript
  transcript="$(_make_transcript_with_skill)"
  _run_guard "gh pr comment 600 -R es6kr/skills --body-file $body_file" "$transcript"
  [ "$status" -eq 0 ]
}

@test "body with the link TEXT only (skill never invoked) is still DENIED — closes the template-text loophole" {
  # This is the exact gap the sibling guard (block-noncompliant-review-comment.sh)
  # has: it only checks the body for the literal string, which a template always
  # carries regardless of whether the skill was invoked.
  local body_file="$TESTDIR/body.md"
  _review_body > "$body_file"
  local transcript
  transcript="$(_make_transcript_without_skill)"
  grep -q "receiving-code-review" "$body_file"
  _run_guard "gh pr comment 600 -R es6kr/skills --body-file $body_file" "$transcript"
  [ "$status" -eq 2 ]
}

@test "non-review-flavored PR comment is not blocked" {
  local body_file="$TESTDIR/body.md"
  printf 'Rebased onto develop, CI green now.\n' > "$body_file"
  local transcript
  transcript="$(_make_transcript_without_skill)"
  _run_guard "gh pr comment 600 -R es6kr/skills --body-file $body_file" "$transcript"
  [ "$status" -eq 0 ]
}

@test "gh pr review (Formal Review) without receiving-code-review is DENIED" {
  local body_file="$TESTDIR/body.md"
  _review_body > "$body_file"
  local transcript
  transcript="$(_make_transcript_without_skill)"
  _run_guard "gh pr review 600 -R es6kr/skills --comment --body-file $body_file" "$transcript"
  [ "$status" -eq 2 ]
}

@test "explicit override env var bypasses the guard" {
  local body_file="$TESTDIR/body.md"
  _review_body > "$body_file"
  local transcript
  transcript="$(_make_transcript_without_skill)"
  cd "$TESTDIR"
  run env ALLOW_REVIEW_POST_WITHOUT_RECEIVING_CODE_REVIEW=1 bash "$GUARD" <<EOF
{"tool_name":"Bash","tool_input":{"command":$(printf '%s' "gh pr comment 600 -R es6kr/skills --body-file $body_file" | jq -Rs .)},"transcript_path":$(printf '%s' "$transcript" | jq -Rs .)}
EOF
  [ "$status" -eq 0 ]
}

@test "unparseable/empty command does not block" {
  cd "$TESTDIR"
  run bash "$GUARD" <<'EOF'
{"tool_name":"Bash","tool_input":{}}
EOF
  [ "$status" -eq 0 ]
}
