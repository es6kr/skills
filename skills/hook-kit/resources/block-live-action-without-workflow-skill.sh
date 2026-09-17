#!/usr/bin/env bash
# PreToolUse:Bash + PreToolUse:mcp__playwright__browser_{navigate,click,type,
# fill_form,press_key,select_option,drag,drop,file_upload,handle_dialog} —
# block a state-mutating live action taken against a tracked workspace item
# (fix_plan.md / checklist.md / task.md) when the session has no evidence of
# having invoked Skill("code-workflow") first.
#
# Background: (see failed-attempts.md "risky-complex-task-live-commands-
# without-code-workflow-plan") — a Prevention rule asking the agent to
# self-apply this gate recurred 4 times because nothing enforced it
# mechanically. This hook is the structural gate.
#
# Scope narrowing (keeps false positives low): only fires when (a) the tool
# call matches a curated mutating-command pattern (Bash) or is itself an
# interactive/navigating browser tool, AND (b) the transcript shows a
# tracker file was Read this session. Read-only verification commands
# (kubectl get/describe/logs, curl GET, git status, etc.) never match (a).
# Sessions with no tracker file in play never match (b) — this hook does not
# guard general-purpose browsing or shell use, only tracker-driven live work.
#
# Bypass: none by design — the required action (invoke the workflow skill
# once per session before the first live action) is cheap and the whole
# point of the gate. If a legitimate exception surfaces, add it here later
# with the specific case documented.

set -uo pipefail

if [ "${1:-}" = "--test" ]; then
  PASS=0; FAIL=0; FAILED_NAMES=()
  TMPDIR_T=$(mktemp -d)
  trap 'rm -rf "$TMPDIR_T"' EXIT

  # Builds a fake transcript JSONL: optional Read(tracker) line, optional
  # Skill(...) line, one per arg ("tracker", "skill:<name>").
  make_transcript() {
    local f="$TMPDIR_T/t_$RANDOM.jsonl"
    for spec in "$@"; do
      case "$spec" in
        tracker)
          jq -nc '{type:"assistant",message:{content:[{type:"tool_use",name:"Read",input:{file_path:"/repo/.agents/fix_plan.md"}}]}}' >> "$f"
          ;;
        tracker-checklist)
          jq -nc '{type:"assistant",message:{content:[{type:"tool_use",name:"Read",input:{file_path:"/repo/checklist.md"}}]}}' >> "$f"
          ;;
        tracker-task)
          jq -nc '{type:"assistant",message:{content:[{type:"tool_use",name:"Read",input:{file_path:"/repo/task.md"}}]}}' >> "$f"
          ;;
        tracker-my-checklist)
          jq -nc '{type:"assistant",message:{content:[{type:"tool_use",name:"Read",input:{file_path:"/repo/my_checklist.md"}}]}}' >> "$f"
          ;;
        tracker-todo)
          jq -nc '{type:"assistant",message:{content:[{type:"tool_use",name:"Read",input:{file_path:"/repo/TODO.md"}}]}}' >> "$f"
          ;;
        skill:*)
          local name="${spec#skill:}"
          jq -nc --arg n "$name" '{type:"assistant",message:{content:[{type:"tool_use",name:"Skill",input:{skill:$n}}]}}' >> "$f"
          ;;
        unrelated-read)
          jq -nc '{type:"assistant",message:{content:[{type:"tool_use",name:"Read",input:{file_path:"/repo/README.md"}}]}}' >> "$f"
          ;;
      esac
    done
    echo "$f"
  }

  test_case_bash() {
    local name="$1" expected="$2" cmd="$3" transcript="${4:-}" actual
    local payload
    if [ -n "$transcript" ]; then
      payload=$(jq -nc --arg c "$cmd" --arg t "$transcript" '{tool_name:"Bash",tool_input:{command:$c},transcript_path:$t}')
    else
      payload=$(jq -nc --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c}}')
    fi
    set +e
    printf '%s' "$payload" | bash "$0" >/dev/null 2>&1
    actual=$?
    set -e
    if [ "$actual" = "$expected" ]; then
      echo "  PASS: $name"; PASS=$((PASS+1))
    else
      echo "  FAIL: $name (expected=$expected got=$actual)"; FAIL=$((FAIL+1)); FAILED_NAMES+=("$name")
    fi
  }

  test_case_tool() {
    local name="$1" expected="$2" tool="$3" transcript="${4:-}" actual
    local payload
    if [ -n "$transcript" ]; then
      payload=$(jq -nc --arg tn "$tool" --arg t "$transcript" '{tool_name:$tn,tool_input:{},transcript_path:$t}')
    else
      payload=$(jq -nc --arg tn "$tool" '{tool_name:$tn,tool_input:{}}')
    fi
    set +e
    printf '%s' "$payload" | bash "$0" >/dev/null 2>&1
    actual=$?
    set -e
    if [ "$actual" = "$expected" ]; then
      echo "  PASS: $name"; PASS=$((PASS+1))
    else
      echo "  FAIL: $name (expected=$expected got=$actual)"; FAIL=$((FAIL+1)); FAILED_NAMES+=("$name")
    fi
  }

  echo "=== Positive fixtures (should block, exit 2) ==="
  T1=$(make_transcript tracker)
  test_case_bash "kubectl apply + tracker read + no skill call" 2 \
    "kubectl apply -f authentik.yaml" "$T1"
  T2=$(make_transcript tracker-checklist)
  test_case_bash "terraform apply + checklist read + no skill call" 2 \
    "terraform apply -auto-approve" "$T2"
  T3=$(make_transcript tracker)
  test_case_tool "browser_navigate + tracker read + no skill call" 2 \
    "mcp__playwright__browser_navigate" "$T3"
  T4=$(make_transcript tracker)
  test_case_bash "wmux browser click + tracker read + no skill call" 2 \
    'node "$WMUX_CLI" browser click @e3' "$T4"
  T_CURL_DATA=$(make_transcript tracker)
  test_case_bash "curl --data + tracker read + no skill call" 2 \
    'curl -s --data "{\"k\":\"v\"}" https://api.example.com' "$T_CURL_DATA"
  T_CURL_REQ=$(make_transcript tracker)
  test_case_bash "curl --request POST + tracker read + no skill call" 2 \
    'curl -s --request POST https://api.example.com' "$T_CURL_REQ"
  T_TASK=$(make_transcript tracker-task)
  test_case_bash "kubectl apply + task.md read + no skill call" 2 \
    "kubectl apply -f authentik.yaml" "$T_TASK"

  echo ""
  echo "=== Negative fixtures (should allow, exit 0) ==="
  test_case_bash "kubectl get (read-only), no transcript" 0 \
    "kubectl get pods -n authentik"
  T5=$(make_transcript tracker)
  test_case_bash "kubectl get + tracker read — still read-only, never matches risky regex" 0 \
    "kubectl get pods -n authentik" "$T5"
  test_case_bash "risky command, no transcript at all (degrade safe)" 0 \
    "kubectl apply -f x.yaml"
  test_case_bash "risky command, transcript has no tracker read" 0 \
    "kubectl apply -f x.yaml" "$(make_transcript unrelated-read)"
  test_case_bash "risky command + my_checklist.md read (not documented tracker)" 0 \
    "kubectl apply -f x.yaml" "$(make_transcript tracker-my-checklist)"
  test_case_bash "risky command + TODO.md read (not documented tracker)" 0 \
    "kubectl apply -f x.yaml" "$(make_transcript tracker-todo)"
  T6=$(make_transcript tracker skill:code-workflow)
  test_case_bash "risky command + tracker read + Skill(code-workflow) called" 0 \
    "terraform apply" "$T6"
  T7=$(make_transcript tracker skill:es6kr:code-workflow)
  test_case_tool "browser_navigate + tracker read + Skill(code-workflow) called (namespaced)" 0 \
    "mcp__playwright__browser_navigate" "$T7"
  test_case_tool "browser_snapshot (read-only browser tool, not matched by design)" 0 \
    "mcp__playwright__browser_snapshot" "$(make_transcript tracker)"
  test_case_bash "curl GET, no method flag, not mutating" 0 \
    "curl -s https://example.com/health"

  echo ""
  echo "PASS=$PASS FAIL=$FAIL"
  if [ "$FAIL" -gt 0 ]; then printf 'failed: %s\n' "${FAILED_NAMES[@]}"; exit 1; fi
  exit 0
fi

INPUT=$(cat)

TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[ -n "$TOOL_NAME" ] || exit 0

# --- 1. Is this call itself a candidate mutating action? ---
RISKY=0
if [ "$TOOL_NAME" = "Bash" ]; then
  COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
  if printf '%s' "$COMMAND" | grep -qiE \
    'kubectl[[:space:]]+(apply|create|delete|patch|replace|exec)|terraform[[:space:]]+apply|docker[[:space:]]+(exec|rm|stop|kill|run)|git[[:space:]]+push|gh[[:space:]]+(pr[[:space:]]+merge|issue[[:space:]]+close|release)|curl[^|]*(-X[[:space:]]*|--request[[:space:]]+)['"'"'"]?(POST|PUT|PATCH|DELETE)|curl[^|]*(--data|-d([[:space:]=]|['"'"'"]))|ak[[:space:]]+shell|vault[[:space:]]+kv[[:space:]]+put|kubectl[[:space:]]+create[[:space:]]+secret|wmux[[:space:]]+browser[[:space:]]+(open|click|type|fill)|browser[[:space:]]+(click|type|fill)'; then
    RISKY=1
  fi
elif printf '%s' "$TOOL_NAME" | grep -qE '^mcp__playwright__browser_(navigate|click|type|fill_form|press_key|select_option|drag|drop|file_upload|handle_dialog)$'; then
  RISKY=1
fi
[ "$RISKY" = "1" ] || exit 0

TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
[ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ] || exit 0

# --- 2. Was a workspace tracker file Read this session? (scope narrowing) ---
TRACKER_SEEN=0
while IFS= read -r line; do
  fp=$(printf '%s' "$line" | jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use" and .name=="Read") | .input.file_path // empty' 2>/dev/null)
  if printf '%s' "$fp" | grep -qiE '(^|/)(fix_plan|checklist|task)\.md$'; then
    TRACKER_SEEN=1
    break
  fi
done < "$TRANSCRIPT"
[ "$TRACKER_SEEN" = "1" ] || exit 0

# --- 3. Has Skill("code-workflow") been invoked? ---
SKILL_SEEN=0
while IFS= read -r line; do
  sk=$(printf '%s' "$line" | jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use" and .name=="Skill") | (.input.skill // .input.name // empty)' 2>/dev/null)
  if printf '%s' "$sk" | grep -qiE 'code-workflow'; then
    SKILL_SEEN=1
    break
  fi
done < "$TRANSCRIPT"
[ "$SKILL_SEEN" = "1" ] && exit 0

{
  echo "DENIED: live/mutating action ($TOOL_NAME) on a tracker-driven task without a workflow-skill gate."
  echo ""
  echo "Why blocked:"
  echo "  - A workspace tracker file (fix_plan.md/checklist.md/task.md) was read this"
  echo "    session, and this call would take a state-mutating or hard-to-reverse"
  echo "    action, but no Skill(\"code-workflow\") call has happened yet in this session."
  echo "  - This class of mistake (ad hoc live execution on a complex/irreversible"
  echo "    tracker item, bypassing Research->Plan->User Review->Implement) has"
  echo "    recurred 4 times; see failed-attempts.md"
  echo "    \"risky-complex-task-live-commands-without-code-workflow-plan\"."
  echo ""
  echo "Required action before retrying:"
  echo "  1. Invoke Skill(\"code-workflow\") for this tracker item"
  echo "     (reuse any existing research doc as Prior Knowledge)."
  echo "  2. Get the resulting plan through User Review."
  echo "  3. Only then retry this live action."
} >&2

exit 2
