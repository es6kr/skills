#!/bin/bash
# context-usage-inject.sh — UserPromptSubmit hook: inject context usage into the conversation
#
# Why: the assistant cannot run /context and never sees statusline data, so any
# rule gated on "how full is the session" (e.g. only offer session-cleanup near
# ~50% usage) is unenforceable without a machine-readable signal. This hook
# computes the current context length from the transcript and emits one line of
# additionalContext per user prompt, giving the assistant the same number the
# user sees in their statusline.
#
# Input (stdin): JSON { session_id, transcript_path, cwd, prompt, ... }
# Output (stdout): "Context usage: ~<used>k / <window>k tokens (<pct>%)"
#   UserPromptSubmit stdout is injected as additionalContext (exit 0).
#
# Context length = input_tokens + cache_creation_input_tokens
#                + cache_read_input_tokens of the LAST assistant message that
#   carries usage data (same basis statusline tools use).
# Window resolution:
#   1. $CC_CONTEXT_WINDOW env override (integer tokens), else
#   2. model-id heuristic: fable/mythos/opus/sonnet-5 -> 1000000 (1M-context tiers),
#      anything else -> 200000.
# Fail-open: any parse error exits 0 with no output (never blocks the prompt).

INPUT=$(cat)

PY=""
for _c in python3 python; do
  if command -v "$_c" >/dev/null 2>&1 && "$_c" -c "pass" >/dev/null 2>&1; then
    PY="$_c"; break
  fi
done
[ -n "$PY" ] || exit 0

export CLAUDE_HOOK_INPUT="$INPUT"
"$PY" - <<'PYEOF' 2>/dev/null || exit 0
import json, os, sys

try:
    payload = json.loads(os.environ.get("CLAUDE_HOOK_INPUT", "{}"))
    path = payload.get("transcript_path", "")
    if not path or not os.path.isfile(path):
        sys.exit(0)

    last_usage, last_model = None, ""
    with open(path) as f:
        for line in f:
            if '"usage"' not in line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("type") != "assistant":
                continue
            u = e.get("message", {}).get("usage")
            if u and u.get("input_tokens") is not None:
                last_usage = u
                last_model = e.get("message", {}).get("model", "") or last_model

    if not last_usage:
        sys.exit(0)

    used = (last_usage.get("input_tokens", 0)
            + last_usage.get("cache_creation_input_tokens", 0)
            + last_usage.get("cache_read_input_tokens", 0))

    env_win = os.environ.get("CC_CONTEXT_WINDOW", "")
    if env_win.isdigit():
        window = int(env_win)
    elif any(t in last_model for t in ("fable", "mythos", "opus", "sonnet-5")):
        window = 1_000_000
    else:
        window = 200_000

    pct = used / window * 100
    print(f"Context usage: ~{used // 1000}k / {window // 1000}k tokens ({pct:.1f}%)")
except Exception:
    sys.exit(0)
PYEOF
exit 0
