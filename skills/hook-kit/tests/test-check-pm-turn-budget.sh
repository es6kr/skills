#!/usr/bin/env bash
# Regression tests for check-pm-turn-budget.py.
#
# The guard is registered as PostToolUse on the Bash matcher only, so a Bash
# command string is its sole activation signal. It activated on any command
# containing the substring "--pm" together with "fix_plan"/"fix-plan"
# anywhere, and the resulting is_pm flag was sticky for the whole session.
# Consequently `grep -n -- '--pm' <path>/fix_plan.md` — a read-only search for
# the literal flag — put the session into PM mode permanently and the budget
# warning then fired every ten tool calls for the rest of the session.
# Mentioning the pipeline is not invoking it.
#
# Run:  bash skills/hook-kit/tests/test-check-pm-turn-budget.sh
# Exit: 0 = all pass, 1 = any fail.

set -u
HOOK_PY="$(cd "$(dirname "$0")/.." && pwd)/resources/check-pm-turn-budget.py"
[[ -f "$HOOK_PY" ]] || { echo "hook not found: $HOOK_PY" >&2; exit 1; }

FAIL=0
PASS=0

# Run one scenario in an isolated HOME so the guard's state file never touches
# the real one. Prints "ACTIVE"/"INACTIVE" and the warning text, if any.
#   probe <expect: active|inactive> <label> <command> [env assignments...]
probe() {
  local expect="$1" label="$2" cmd="$3"; shift 3
  local out
  out="$(env -i PATH="$PATH" HOME="$(mktemp -d)" "$@" python3 - "$HOOK_PY" "$cmd" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("guard", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
msg = m.track_pm_budget("Bash", {"command": sys.argv[2]}, "unit-session")
state = m.get_state().get("unit-session", {})
print("ACTIVE" if state.get("is_pm") else "INACTIVE")
print("MSG" if msg else "NOMSG")
PY
)"
  local got; got="$(printf '%s\n' "$out" | sed -n 1p)"
  local want="ACTIVE"; [[ "$expect" == "inactive" ]] && want="INACTIVE"
  if [[ "$got" == "$want" ]]; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
    echo "FAIL [$label]: expected $want, got ${got:-<empty>}" >&2
    echo "       cmd: $cmd" >&2
  fi
}

echo "--- false positives: the command only mentions the pipeline ---"
probe inactive "grep for the literal --pm flag in the tracker" \
  "grep -n -- '--pm' /ws/.agents/fix_plan.md"
probe inactive "ripgrep with --pm as the search pattern" \
  "rg -- '--pm' /ws/.agents/fix_plan.md"
probe inactive "appending prose that mentions fix-plan --pm" \
  "echo 'see the fix-plan --pm pipeline' >> /ws/docs/research.md"
probe inactive "counting matches in a fix_plan path" \
  "grep -c -- '--pm' /ws/.agents/fix_plan.md"

echo "--- true positives: the command actually invokes the pipeline ---"
probe active "python invocation of fix_plan.py --pm" \
  "python3 skills/fix-plan/scripts/fix_plan.py --pm --triage"
probe active "shell invocation with flags before --pm" \
  "bash scripts/fix-plan.sh --dry-run --pm"

echo "--- explicit off switch ---"
# PM_MODE is honoured when truthy; it must also be honoured when falsy, so a
# session that knows the guard does not apply to it can turn the guard off.
probe inactive "PM_MODE=0 overrides an otherwise matching invocation" \
  "python3 scripts/fix_plan.py --pm" PM_MODE=0

echo "--- escalation is bounded ---"
# Once the budget is exceeded the guard warned every tenth call for the rest of
# the session. A false positive therefore cost a warning indefinitely; cap the
# escalations so a wrong activation cannot occupy the whole session.
cap_out="$(env -i PATH="$PATH" HOME="$(mktemp -d)" python3 - "$HOOK_PY" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("guard", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
sess = "cap-session"
m.track_pm_budget("Bash", {"command": "python3 scripts/fix_plan.py --pm"}, sess)
warns = 0
for _ in range(200):
    if m.track_pm_budget("Bash", {"command": "echo step"}, sess):
        warns += 1
print(warns)
PY
)"
if [[ "${cap_out:-999}" -le 4 ]]; then
  PASS=$((PASS + 1))
else
  FAIL=$((FAIL + 1))
  echo "FAIL [escalation cap]: expected at most 4 warnings over 200 calls, got $cap_out" >&2
fi

echo "--- the warning tells the agent to classify the session first ---"
# The budget targets a session that performs the PM role. A session that
# builds or measures the PM role itself is a different thing and the guard
# cannot tell them apart, so the message must say to check that before
# handing off, rather than asserting the handoff unconditionally.
msg_out="$(env -i PATH="$PATH" HOME="$(mktemp -d)" python3 - "$HOOK_PY" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("guard", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
sess = "msg-session"
m.track_pm_budget("Bash", {"command": "python3 scripts/fix_plan.py --pm"}, sess)
msg = None
while msg is None:
    msg = m.track_pm_budget("Bash", {"command": "echo step"}, sess)
print(msg)
PY
)"
if printf '%s' "$msg_out" | grep -qiE 'classif|session type|building or measuring|false positive'; then
  PASS=$((PASS + 1))
else
  FAIL=$((FAIL + 1))
  echo "FAIL [message session-type check]: warning does not ask the agent to classify the session" >&2
fi

echo "--- regressions: existing behaviour preserved ---"
probe inactive "an unrelated command does not activate" "git status"
probe active "PM_MODE=1 activates without any fix-plan reference" \
  "git status" PM_MODE=1

echo
echo "passed=$PASS failed=$FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
