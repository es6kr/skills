#!/bin/bash
# context-usage-inject.sh — UserPromptSubmit hook: inject context usage into the conversation
# Supports both Claude Code (token usage telemetry) and Antigravity/Gemini (transcript compaction-aware).
#
# Input (stdin): JSON { session_id, transcript_path, cwd, prompt, ... }
# Output (stdout): "Context usage: ~<used>k / <window>k tokens (<pct>%)"

INPUT=$(cat)

# Interpreter resolution: probe for a WORKING python
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
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    payload = json.loads(os.environ.get("CLAUDE_HOOK_INPUT", "{}"))
    path = payload.get("transcript_path", "")
    if not path or not os.path.isfile(path):
        sys.exit(0)

    is_antigravity = False
    agy_active_steps = []
    
    last_usage, last_model, last_ts = None, "", None
    prev_total, marker_since_usage, marker_gap_drop = None, False, False

    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue

            # Antigravity format detection
            src = entry.get("source", "")
            if "step_index" in entry or src in ("MODEL", "USER_EXPLICIT", "SYSTEM"):
                is_antigravity = True
                content = entry.get("content", "") or ""
                # True compaction marker from system/user harness (never model assistant text)
                if src in ("SYSTEM", "USER_EXPLICIT", "USER") and "<CONTEXT_SUMMARY>" in content:
                    agy_active_steps = [entry]
                else:
                    agy_active_steps.append(entry)
                continue

            # Claude Code format
            if '"isCompactSummary"' in line or '"compact_boundary"' in line or entry.get("subtype") == "compact_boundary":
                last_usage = None
                last_model = ""
                last_ts = None
                marker_since_usage = True
                continue

            if entry.get("type") == "assistant":
                msg = entry.get("message", {}) or {}
                usage = msg.get("usage")
                if isinstance(usage, dict) and any(k in usage for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")):
                    cur_total = sum(int(usage.get(k, 0) or 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                    if prev_total is not None and cur_total < prev_total:
                        marker_gap_drop = True
                    prev_total = cur_total
                    last_usage = usage
                    last_model = msg.get("model", "") or last_model
                    last_ts = entry.get("timestamp") or last_ts
                    marker_since_usage = False

    if is_antigravity:
        content_chars = 0
        for s in agy_active_steps:
            content_chars += len(s.get("content", "") or "")
        
        base_overhead = int(os.environ.get("ANTIGRAVITY_BASE_TOKENS", os.environ.get("CC_BASE_TOKENS", "0")))
        content_tokens = round(content_chars / 3.5)
        total_tokens = base_overhead + content_tokens
        
        window = int(os.environ.get("CC_CONTEXT_WINDOW", "1000000"))
        pct = round((total_tokens / window) * 100, 1)
        used_k = round(total_tokens / 1000, 1)
        win_k = window // 1000

        print(f"Context usage: ~{used_k}k / {win_k}k tokens ({pct}%)")
        
        cleanup_pct = float(os.environ.get("CC_CLEANUP_RECOMMEND_PCT", "40.0"))
        if pct >= cleanup_pct:
            print(f"[CLEANUP-GATE] Context usage is at/above threshold ({pct}% >= {cleanup_pct}%). Recommend /cleanup.")
        sys.exit(0)

    if not last_usage:
        sys.exit(0)

    input_tok = int(last_usage.get("input_tokens", 0) or 0)
    cache_create = int(last_usage.get("cache_creation_input_tokens", 0) or 0)
    cache_read = int(last_usage.get("cache_read_input_tokens", 0) or 0)
    total_tokens = input_tok + cache_create + cache_read

    model_lower = (last_model or "").lower()
    if os.environ.get("CC_CONTEXT_WINDOW"):
        try:
            window = int(os.environ["CC_CONTEXT_WINDOW"])
        except ValueError:
            window = 200000
    elif any(k in model_lower for k in ("fable", "mythos", "opus", "sonnet-5")):
        window = 1000000
    else:
        window = 200000

    pct = round((total_tokens / window) * 100, 1)
    used_k = round(total_tokens / 1000, 1)
    win_k = window // 1000

    print(f"Context usage: ~{used_k}k / {win_k}k tokens ({pct}%)")
    cleanup_pct = float(os.environ.get("CC_CLEANUP_RECOMMEND_PCT", "50.0"))
    if pct >= cleanup_pct:
        print(f"[CLEANUP-GATE] Context usage is at/above threshold ({pct}% >= {cleanup_pct}%). Recommend /cleanup.")

except Exception:
    sys.exit(0)
PYEOF
