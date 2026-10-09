#!/bin/bash
# block-orca-split-without-ask.sh (PreToolUse:Bash)
#
# Blocks `orca(-ide|-dev)? terminal split` and `orca(-ide|-dev)? repo add`
# unless a recent AskUserQuestion call in this session's transcript already
# named a harness/model AND something about this specific split/registration
# (workspace, repo, pane, split keyword — including Korean equivalents, see
# split-scope-ko.regex alongside this script).
#
# Why: failed-attempts.md class=cross-workspace-task-orca-split-ask-omission
# has recurred 5 times (Hermes x4, Claude Code x1) — approving WHAT to do
# ("investigate X", a slash command, a prior direction-only ask) kept getting
# read as also approving HOW to do it (which workspace/repo to register,
# which harness/model, which pane role) for the orca split/registration
# itself. The sibling hooks guard adjacent but distinct points:
#   - block-orca-new-tab-without-split-check.sh: split-vs-new-tab choice
#   - block-orca-ask-without-split-option.sh: the ask must OFFER a split option
# Neither checks whether an ask asking about harness/model/workspace for THIS
# split/repo-add actually happened. This hook is that missing check.
#
# `orca repo add` has no undo CLI command (per the orca skill's own launch.md),
# so it gets the same gate as terminal split — not a lighter one.

input=$(cat)

orca_bin_pattern='orca-ide|orca-dev|orca'
if [ -n "$ORCA_CLI_COMMAND" ]; then
  orca_cli_escaped=$(printf '%s' "$ORCA_CLI_COMMAND" | sed 's/[][\.^$*+()?{}|/]/\\&/g')
  orca_bin_pattern="${orca_cli_escaped}|${orca_bin_pattern}"
fi

command=$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("")
    sys.exit(0)
ti = d.get("tool_input") or {}
print(ti.get("command") or d.get("command") or "")
' 2>/dev/null)

[ -z "$command" ] && exit 0

sanitized_command=$(printf '%s' "$command" | sed -E "s/'[^']*'//g; s/\"[^\"]*\"//g")

is_split=0
is_repo_add=0
echo "$sanitized_command" | grep -qE "(^|[;&|]\s*)(${orca_bin_pattern})[[:space:]]+terminal[[:space:]]+split\b" && is_split=1
echo "$sanitized_command" | grep -qE "(^|[;&|]\s*)(${orca_bin_pattern})[[:space:]]+repo[[:space:]]+add\b" && is_repo_add=1

if [ "$is_split" -eq 0 ] && [ "$is_repo_add" -eq 0 ]; then
  exit 0
fi

echo "$sanitized_command" | grep -qE 'ORCA_ASK_CONFIRMED=1' && exit 0

transcript_path=$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("")
    sys.exit(0)
print(d.get("transcript_path") or "")
' 2>/dev/null)

[ -n "$transcript_path" ] && [ -f "$transcript_path" ] || exit 0

last_ask_text=$(python3 -c '
import json, sys

path = sys.argv[1]
last = None
try:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if entry.get("type") != "assistant":
                continue
            content = (entry.get("message") or {}).get("content") or []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use":
                    continue
                if block.get("name") != "AskUserQuestion":
                    continue
                last = block.get("input") or {}
except Exception:
    pass

if last is None:
    print("")
    sys.exit(0)

out = []
for q in (last.get("questions") or []):
    out.append(q.get("question") or "")
    out.append(q.get("header") or "")
    for o in (q.get("options") or []):
        out.append(o.get("label") or "")
        out.append(o.get("description") or "")
print("\n".join(out))
' "$transcript_path" 2>/dev/null)

[ -z "$last_ask_text" ] && last_ask_text=""

harness_model_token='claude|opus|sonnet|haiku|fable|antigravity|openclaw|codex|gemini|cursor'
split_scope_token='split|repo[[:space:]]*add|workspace|worktree|pane'
ko_tokens_file="$(dirname "$0")/split-scope-ko.regex"
if [ -f "$ko_tokens_file" ]; then
  ko_tokens=$(grep -vE '^\s*#|^\s*$' "$ko_tokens_file" | paste -sd'|' -)
  [ -n "$ko_tokens" ] && split_scope_token="${split_scope_token}|${ko_tokens}"
fi

harness_hit=0
scope_hit=0
echo "$last_ask_text" | grep -qiE "$harness_model_token" && harness_hit=1
echo "$last_ask_text" | grep -qiE "$split_scope_token" && scope_hit=1

if [ "$harness_hit" -eq 1 ] && [ "$scope_hit" -eq 1 ]; then
  exit 0
fi

cat >&2 <<'EOF'
============================================================
⛔ [Safety Hook] BLOCKED: orca terminal split / repo add without a dedicated prior ask.

Why blocked:
  - failed-attempts.md class=cross-workspace-task-orca-split-ask-omission has
    recurred 5 times: a direction-only approval (slash command, prior ask, or
    an earlier "what to do" decision) got read as also approving the split's
    workspace/repo, harness, model, and pane role.
  - The most recent AskUserQuestion in this session's transcript does not
    mention both (a) a harness/model keyword and (b) something about this
    split/repo-add/workspace — so it cannot be the confirming ask for this
    specific action.

Required action (pick one):
  1. Call AskUserQuestion now, naming the target workspace/repo path, harness
     tool, model, and each pane's role, then retry this command.
  2. If this exact ask already happened through a medium this hook cannot see
     (e.g. relayed from another session), prefix the command with the literal
     text ORCA_ASK_CONFIRMED=1 so the opt-out is auditable.

Reference: failed-attempts.md class=cross-workspace-task-orca-split-ask-omission.
============================================================
EOF
exit 2
