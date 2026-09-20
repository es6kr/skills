#!/usr/bin/env bats
# Regression test for the audit-annotation-append exemption in
# plan-undecided-guard.sh.
#
# The hazard: an Edit that appends an audit/review section (heading matching
# "## ... 감사" / "## ... Audit") to a plan-*.md file routinely discusses
# trade-offs and prior recommendations in past tense while reviewing
# already-decided content. The guard's undecided-marker prose patterns
# ("recommend", " vs ", "Trade-offs") read that as a fresh live decision and
# fire on every such append — observed 15+ times in one session
# (improvements.md 2026-08-25 Step 2-B finding).

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/code-workflow/resources/plan-undecided-guard.sh"

setup() {
  [ -f "$GUARD" ] || skip "guard not found: $GUARD"
  command -v jq >/dev/null || skip "jq not available"
}

run_guard() {
  local tool_name="$1" file_path="$2" body_key="$3" body="$4"
  local payload
  payload="$(jq -nc --arg t "$tool_name" --arg f "$file_path" --arg k "$body_key" --arg b "$body" \
    '{tool_name:$t, tool_input:({file_path:$f} + {($k):$b})}')"
  printf '%s' "$payload" | bash "$GUARD" >/dev/null 2>&1
  echo $?
}

# --- exempted: Edit appending an audit section --------------------------

@test "Edit appending a Korean audit heading with trade-off prose is exempted" {
  body='## 2026-09-19 감사

이전 선택을 재검토했다. 옵션 A vs 옵션 B 중 A를 recommend한 근거는 다음과 같다.'
  result="$(run_guard "Edit" "/repo/docs/generated/plan-foo.md" "new_string" "$body")"
  [ "$result" -eq 0 ]
}

@test "Edit appending an English Audit heading with trade-off prose is exempted" {
  body='## Audit — 2026-09-19

Re-reviewed the prior Trade-offs table; recommend keeping the original choice.'
  result="$(run_guard "Edit" "/repo/docs/generated/plan-foo.md" "new_string" "$body")"
  [ "$result" -eq 0 ]
}

# --- still caught: genuine undecided content, no audit heading ----------

@test "Edit without an audit heading still fires on undecided markers" {
  body='Option A vs Option B — TBD, decision required before proceeding.'
  result="$(run_guard "Edit" "/repo/docs/generated/plan-foo.md" "new_string" "$body")"
  [ "$result" -eq 2 ]
}

# --- scoping: exemption is Edit-only, not Write --------------------------

@test "Write with an audit heading is NOT exempted (full-file scope)" {
  body='## 감사

recommend A vs B, decision required.'
  result="$(run_guard "Write" "/repo/docs/generated/plan-foo.md" "content" "$body")"
  [ "$result" -eq 2 ]
}

@test "Edit with audit heading AND undecided markers outside audit section still fires" {
  body='## Audit — 2026-09-19

Re-reviewed the prior Trade-offs table; recommend keeping the original choice.

## Open Questions

Option A vs Option B — TBD, decision required before proceeding.'
  result="$(run_guard "Edit" "/repo/docs/generated/plan-foo.md" "new_string" "$body")"
  [ "$result" -eq 2 ]
}

# --- non-plan path is always a no-op -------------------------------------

@test "non-plan file path is always allowed regardless of content" {
  body='## 감사

recommend A vs B, decision required.'
  result="$(run_guard "Edit" "/repo/README.md" "new_string" "$body")"
  [ "$result" -eq 0 ]
}

