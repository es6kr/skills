#!/usr/bin/env bash
# Tests for check-slash-command-skill-invoked.sh (Stop hook).
#
# Verifies that slash-command invocations (both bare and plugin-namespaced,
# e.g. `/task-flow` and `/es6kr:task-flow`) properly require a corresponding
# Skill() tool call before the turn concludes.
#
# Run:  bash skills/hook-kit/tests/test-check-slash-command-skill-invoked.sh
# Exit: 0 = all pass, 1 = any fail.

set -u
HOOK="$(cd "$(dirname "$0")/.." && pwd)/resources/check-slash-command-skill-invoked.sh"
[[ -f "$HOOK" ]] || { echo "hook not found: $HOOK" >&2; exit 1; }

TESTDIR="$(mktemp -d)"
MOCK_HOME="$TESTDIR/home"
mkdir -p "$MOCK_HOME/.agents/skills/task-flow"
mkdir -p "$MOCK_HOME/.agents/skills/cleanup"
trap 'rm -rf "$TESTDIR"' EXIT

FAIL=0

run_hook() {
  local transcript="$1"
  local input="{\"transcript_path\":\"$transcript\"}"
  HOME="$MOCK_HOME" bash "$HOOK" <<< "$input" 2>/dev/null
}

check_decision() {
  local name="$1"
  local want_decision="$2" # "allow" or "block"
  local output="$3"

  local is_block="false"
  if printf '%s' "$output" | grep -q '"decision":\s*"block"'; then
    is_block="true"
  fi

  if [[ "$want_decision" == "block" && "$is_block" == "true" ]]; then
    echo "PASS  $name (blocked as expected)"
  elif [[ "$want_decision" == "allow" && "$is_block" == "false" ]]; then
    echo "PASS  $name (allowed as expected)"
  else
    echo "FAIL  $name (want=$want_decision, got output: $output)"
    FAIL=1
  fi
}

# -----------------------------------------------------------------------------
# Case 1: Bare command (/task-flow) followed by matching bare Skill call
# -----------------------------------------------------------------------------
T1="$TESTDIR/t1.jsonl"
cat > "$T1" <<'EOF'
{"type":"user","message":{"content":"<command-name>/task-flow</command-name> Let's do research"}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"task-flow"}}]}}
EOF
check_decision "case 1: bare command with matching bare Skill call" "allow" "$(run_hook "$T1")"

# -----------------------------------------------------------------------------
# Case 2: Bare command (/task-flow) WITHOUT Skill call
# -----------------------------------------------------------------------------
T2="$TESTDIR/t2.jsonl"
cat > "$T2" <<'EOF'
{"type":"user","message":{"content":"<command-name>/task-flow</command-name> Let's do research"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"I will just summarize directly."}]}}
EOF
check_decision "case 2: bare command without Skill call" "block" "$(run_hook "$T2")"

# -----------------------------------------------------------------------------
# Case 3: Namespaced command (/es6kr:task-flow) with matching namespaced Skill call
# -----------------------------------------------------------------------------
T3="$TESTDIR/t3.jsonl"
cat > "$T3" <<'EOF'
{"type":"user","message":{"content":"<command-name>/es6kr:task-flow</command-name> Let's do research"}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"es6kr:task-flow"}}]}}
EOF
check_decision "case 3: namespaced command with matching namespaced Skill call" "allow" "$(run_hook "$T3")"

# -----------------------------------------------------------------------------
# Case 4: Namespaced command (/es6kr:task-flow) with bare Skill call
# -----------------------------------------------------------------------------
T4="$TESTDIR/t4.jsonl"
cat > "$T4" <<'EOF'
{"type":"user","message":{"content":"<command-name>/es6kr:task-flow</command-name> Let's do research"}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"task-flow"}}]}}
EOF
check_decision "case 4: namespaced command with bare Skill call" "allow" "$(run_hook "$T4")"

# -----------------------------------------------------------------------------
# Case 5: Bare command (/task-flow) with namespaced Skill call
# -----------------------------------------------------------------------------
T5="$TESTDIR/t5.jsonl"
cat > "$T5" <<'EOF'
{"type":"user","message":{"content":"<command-name>/task-flow</command-name> Let's do research"}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"es6kr:task-flow"}}]}}
EOF
check_decision "case 5: bare command with namespaced Skill call" "allow" "$(run_hook "$T5")"

# -----------------------------------------------------------------------------
# Case 6: Namespaced command (/es6kr:task-flow) WITHOUT Skill call
# -----------------------------------------------------------------------------
T6="$TESTDIR/t6.jsonl"
cat > "$T6" <<'EOF'
{"type":"user","message":{"content":"<command-name>/es6kr:task-flow</command-name> Let's do research"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"I will just summarize directly."}]}}
EOF
check_decision "case 6: namespaced command without Skill call" "block" "$(run_hook "$T6")"

# -----------------------------------------------------------------------------
# Case 7: Uninstalled / native command (/compact) without Skill call
# -----------------------------------------------------------------------------
T7="$TESTDIR/t7.jsonl"
cat > "$T7" <<'EOF'
{"type":"user","message":{"content":"<command-name>/compact</command-name>"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"Compacting session."}]}}
EOF
check_decision "case 7: uninstalled native command without Skill call" "allow" "$(run_hook "$T7")"

# -----------------------------------------------------------------------------
# Case 8: Quoted command in tool_result without Skill call
# -----------------------------------------------------------------------------
T8="$TESTDIR/t8.jsonl"
cat > "$T8" <<'EOF'
{"type":"user","message":{"content":[{"type":"tool_result","content":"Prior doc mentioned <command-name>/task-flow</command-name>"}]}}
{"type":"assistant","message":{"content":[{"type":"text","text":"Acknowledged."}]}}
EOF
check_decision "case 8: quoted command in tool_result" "allow" "$(run_hook "$T8")"

# -----------------------------------------------------------------------------
# Case 9: Quoted command in compact summary without Skill call
# -----------------------------------------------------------------------------
T9="$TESTDIR/t9.jsonl"
cat > "$T9" <<'EOF'
{"type":"user","isCompactSummary":true,"message":{"content":"Previously user ran <command-name>/task-flow</command-name>"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"Understood."}]}}
EOF
check_decision "case 9: quoted command in compact summary" "allow" "$(run_hook "$T9")"

# -----------------------------------------------------------------------------
# Case 10: Slash command (/task-flow) followed by DIFFERENT Skill call
# -----------------------------------------------------------------------------
T10="$TESTDIR/t10.jsonl"
cat > "$T10" <<'EOF'
{"type":"user","message":{"content":"<command-name>/task-flow</command-name> Let's do research"}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"cleanup"}}]}}
EOF
check_decision "case 10: command followed by different Skill call" "block" "$(run_hook "$T10")"

exit "$FAIL"
