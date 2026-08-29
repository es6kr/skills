#!/usr/bin/env bash
# Unit tests for guards-config resolution hierarchy (Option C: Repo Override > PLUGIN_DATA > Default)
set -uo pipefail

HOOK_DIR="$(cd "$(dirname "$0")/../resources" && pwd)"
ASK_GUARD="$HOOK_DIR/ask-guard.sh"
EDIT_GUARD="$HOOK_DIR/edit-guard.sh"
FIXTURE="$(cd "$(mktemp -d)" && pwd -P)"
trap 'rm -rf "$FIXTURE"' EXIT

pass=0
fail=0

check() {
  local name="$1" expected="$2" actual="$3"
  local exp_canon act_canon
  exp_canon="$(cd "$(dirname "$expected")" 2>/dev/null && pwd)/$(basename "$expected")"
  act_canon="$(cd "$(dirname "$actual")" 2>/dev/null && pwd)/$(basename "$actual")"
  if [ "$exp_canon" = "$act_canon" ]; then
    pass=$((pass+1))
    echo "PASS  $name"
  else
    fail=$((fail+1))
    echo "FAIL  $name: expected=[$exp_canon] actual=[$act_canon]"
  fi
}

# Source resolve_guards_config function by extracting it from ask-guard.sh
eval "$(sed -n '/^resolve_guards_config()/,/^}/p' "$ASK_GUARD")"

# T1: Explicit GUARDS_CONFIG env var
mkdir -p "$FIXTURE/custom"
echo '{"version":1}' > "$FIXTURE/custom/guards-config.json"
export GUARDS_CONFIG="$FIXTURE/custom/guards-config.json"
res="$(resolve_guards_config "$FIXTURE" 2>/dev/null || true)"
check "T1 explicit GUARDS_CONFIG env" "$FIXTURE/custom/guards-config.json" "$res"
unset GUARDS_CONFIG

# T2: Repo override (.agents/guards-config.json in git root)
mkdir -p "$FIXTURE/repo-a/.agents"
echo '{"version":1,"repo":"a"}' > "$FIXTURE/repo-a/.agents/guards-config.json"
git -C "$FIXTURE/repo-a" init -q 2>/dev/null || true
res="$(resolve_guards_config "$FIXTURE/repo-a" 2>/dev/null || true)"
check "T2 repo .agents override" "$FIXTURE/repo-a/.agents/guards-config.json" "$res"

# T3: Repo override (.claude/guards-config.json in git root)
mkdir -p "$FIXTURE/repo-b/.claude"
echo '{"version":1,"repo":"b"}' > "$FIXTURE/repo-b/.claude/guards-config.json"
git -C "$FIXTURE/repo-b" init -q 2>/dev/null || true
res="$(resolve_guards_config "$FIXTURE/repo-b" 2>/dev/null || true)"
check "T3 repo .claude override" "$FIXTURE/repo-b/.claude/guards-config.json" "$res"

# T4: Neutral global config (~/.config/agent-workspace/guards-config.json)
mkdir -p "$FIXTURE/fake-home/.config/agent-workspace"
echo '{"version":1,"source":"agent-workspace"}' > "$FIXTURE/fake-home/.config/agent-workspace/guards-config.json"
mkdir -p "$FIXTURE/empty-repo"
REAL_HOME="$HOME"
export HOME="$FIXTURE/fake-home"
res="$(resolve_guards_config "$FIXTURE/empty-repo" 2>/dev/null || true)"
check "T4 agent-workspace SSOT" "$FIXTURE/fake-home/.config/agent-workspace/guards-config.json" "$res"

# T5: Legacy global config fallback (~/.config/plane-backlog/guards-config.json)
rm "$FIXTURE/fake-home/.config/agent-workspace/guards-config.json"
mkdir -p "$FIXTURE/fake-home/.config/plane-backlog"
echo '{"version":1,"source":"plane-backlog"}' > "$FIXTURE/fake-home/.config/plane-backlog/guards-config.json"
res="$(resolve_guards_config "$FIXTURE/empty-repo" 2>/dev/null || true)"
check "T5 plane-backlog migration fallback" "$FIXTURE/fake-home/.config/plane-backlog/guards-config.json" "$res"
rm "$FIXTURE/fake-home/.config/plane-backlog/guards-config.json"

# T6: CLAUDE_PLUGIN_DATA / PLUGIN_DATA persistent storage
mkdir -p "$FIXTURE/plugin-data"
echo '{"version":1,"source":"plugin-data"}' > "$FIXTURE/plugin-data/guards-config.json"
export CLAUDE_PLUGIN_DATA="$FIXTURE/plugin-data"
res="$(resolve_guards_config "$FIXTURE/empty-repo" 2>/dev/null || true)"
check "T6 CLAUDE_PLUGIN_DATA persistent" "$FIXTURE/plugin-data/guards-config.json" "$res"
unset CLAUDE_PLUGIN_DATA

# T7: PLUGIN_DATA alias
export PLUGIN_DATA="$FIXTURE/plugin-data"
res="$(resolve_guards_config "$FIXTURE/empty-repo" 2>/dev/null || true)"
check "T7 PLUGIN_DATA alias" "$FIXTURE/plugin-data/guards-config.json" "$res"
unset PLUGIN_DATA
export HOME="$REAL_HOME"

# T8: Plugin bundled default data/guards-config.json (when no custom global exists)
export HOME="$FIXTURE/fake-home"
res="$(resolve_guards_config "$FIXTURE/empty-repo" 2>/dev/null || true)"
expected_default="$HOOK_DIR/../data/guards-config.json"
check "T8 bundled default fallback" "$expected_default" "$res"
export HOME="$REAL_HOME"

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
