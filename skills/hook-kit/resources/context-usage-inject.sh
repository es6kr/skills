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
# Cleanup-recommend tier: at >= $CC_CLEANUP_RECOMMEND_PCT (default 50) a second
# directive line is injected obligating a /cleanup recommendation at the turn's
# wrap-up. Rationale: the 45% gate lives in next-skill docs and the deny-hook
# (block-cleanup-option-below-context-gate.sh) can only judge asks it can
# classify as wrap-ups — session-tail asks without end/stop wording escaped
# both, so the obligation must ride on the signal itself (context-usage family,
# 6th recurrence — see failed-attempts.md grep "context-usage").
# Fail-open: any parse error exits 0 with no output (never blocks the prompt).
#
# Staleness caveat (context-usage-stale, 18th recurrence): the isCompactSummary
# marker only catches compaction that already happened BEFORE this hook runs.
# UserPromptSubmit fires before the framework's context-setup step for the
# turn, so a compaction triggered DURING that setup (observed: session resumed
# after an 8.4h idle gap, no isCompactSummary marker, hook reported 52.1% while
# the very next assistant call actually ran at 22.5%) is structurally
# invisible to marker-based detection. Mitigated below via a last-usage-age
# check — not a fix for the underlying timing gap (which no amount of transcript
# parsing can close), just a caveat so the reading isn't blindly trusted.
#
# First-post-compact suppression (context-usage-stale, 20th recurrence): the
# isCompactSummary reset above prevents reusing a STALE pre-compact number, but
# the very next reading after that reset can still be a genuinely FRESH, high
# number — one turn of context reconstruction (re-reading skills/files to
# resume working state) inflates usage without representing accumulating
# budget pressure. Observed: a post-compact turn measured 62.7% (real, not
# stale) and still triggered [CLEANUP-GATE], prompting a second cleanup
# recommendation immediately after the session had just been compacted for
# exactly that reason. Fix: suppress [CLEANUP-GATE] specifically on the first
# assistant-usage reading seen since the last isCompactSummary reset,
# regardless of its pct — treat it as effectively < 20% for gating purposes.

INPUT=$(cat)

# Interpreter resolution: probe for a WORKING python, not merely a name on PATH.
# On Windows the `python3` shim is a Microsoft Store stub that exits 49 and
# prints "Python" to stderr — `command -v python3` succeeds while every actual
# run fails, so a name-only check silently disables this hook (fail-open swallows
# the error and no usage line is ever injected).
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

# Writing side needs the same locale-independence as reading: the directive
# text below carries non-ASCII punctuation, and on a cp949 console that raises
# UnicodeEncodeError mid-print — the outer handler then swallows it and only
# the first (ASCII-only) line ever reaches the transcript.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    payload = json.loads(os.environ.get("CLAUDE_HOOK_INPUT", "{}"))
    path = payload.get("transcript_path", "")
    if not path or not os.path.isfile(path):
        sys.exit(0)

    last_usage, last_model, last_ts = None, "", None
    compact_seen = False
    post_compact_usage_count = 0
    # encoding is explicit: Python's default is locale-dependent, so on a
    # non-UTF-8 Windows console codepage (e.g. cp949) any non-ASCII transcript
    # line raises UnicodeDecodeError and the outer handler silently exits —
    # disabling this hook entirely with no diagnostic.
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            # compact-aware: /compact inserts a {"type":"user",...,
            # "isCompactSummary":true} entry with no usage data of its own.
            # Any usage figure from BEFORE this marker describes the
            # pre-compact (inflated) context and must not be reused as if
            # current post-compact size — reset so only a later,
            # post-compact assistant usage entry can repopulate last_usage.
            # (failed-attempts.md class=context-usage-stale 14th/16th
            # recurrence: the fix was documented but never reached this
            # deployed file.)
            if '"isCompactSummary"' in line:
                try:
                    marker = json.loads(line)
                except json.JSONDecodeError:
                    marker = None
                if marker and marker.get("isCompactSummary") is True:
                    last_usage, last_model, last_ts = None, "", None
                    compact_seen = True
                    post_compact_usage_count = 0
                continue
            if '"usage"' not in line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("type") != "assistant":
                continue
            # `or {}` not a dict default: a JSON `"message": null` makes
            # .get("message", {}) return None, and the chained .get raises.
            msg = e.get("message") or {}
            u = msg.get("usage")
            if u and u.get("input_tokens") is not None:
                last_usage = u
                last_model = msg.get("model", "") or last_model
                last_ts = e.get("timestamp")
                if compact_seen:
                    post_compact_usage_count += 1

    if not last_usage:
        # No post-compact assistant usage yet (right after /compact, before
        # this turn's own response) — fail-safe: emit nothing rather than a
        # stale pre-compact figure. The next turn (once an assistant message
        # with usage exists) will inject a fresh, correct number.
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

    # Staleness caveat: this figure is computed from the last usage-bearing
    # assistant message ON RECORD — if that message is old, a compaction may
    # have happened since (session resume after idle, or a compaction path
    # with no isCompactSummary marker) and this hook has no way to see it
    # (UserPromptSubmit runs before the framework's context-setup step for
    # THIS turn). Empirically validated against this session's own history
    # (6 real compaction-sized drops): short gaps (<10min) correlate with
    # explicit /compact (already marker-caught); long gaps (500min) correlate
    # with the undetected case this caveat targets. A long gap with no real
    # drop (one observed case, 371min) is a harmless false positive — it only
    # adds a caveat, never blocks anything.
    stale_min_env = os.environ.get("CC_CONTEXT_STALE_MIN", "")
    stale_min = int(stale_min_env) if stale_min_env.isdigit() else 15
    if last_ts:
        try:
            from datetime import datetime, timezone
            last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            gap_min = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
            if gap_min >= stale_min:
                print(
                    f"[CONTEXT-STALE] This reading is based on an assistant message "
                    f"from ~{gap_min:.0f} min ago. A compaction may have happened "
                    "since (this hook cannot see a compaction that runs after it "
                    "fires) — do not act on a threshold gate (cleanup trigger, "
                    "ralph-loop pacing, etc.) from this figure alone. Wait for this "
                    "turn's own response (carries a fresh, accurate figure) or "
                    "re-invoke this script directly before deciding."
                )
        except Exception:
            pass

    # Recommend threshold is per-model: a larger effective working budget means
    # a higher share of the window can be spent before a wrap-up is worth
    # proposing. Env override wins; otherwise pick by model id.
    rec_env = os.environ.get("CC_CLEANUP_RECOMMEND_PCT", "")
    if rec_env.isdigit():
        rec_pct = int(rec_env)
    elif any(t in last_model for t in ("fable", "mythos")):
        rec_pct = 55
    elif "opus" in last_model:
        rec_pct = 50
    else:
        rec_pct = 45
    # Machine-readable line for consumers that must apply the SAME threshold
    # (e.g. the deny-hook that blocks under/over-offered cleanup options).
    # Opt-in so the normal injected context stays to one human-facing line.
    if os.environ.get("CC_EMIT_THRESHOLD") == "1":
        print(f"CLEANUP-THRESHOLD: {rec_pct}")

    # First-post-compact reading: this is the ONLY assistant-usage entry seen
    # since the last isCompactSummary reset. Its pct is real (not stale) but
    # inflated by one-time context-reconstruction cost rather than
    # accumulating budget pressure — suppress the cleanup recommendation for
    # this one reading regardless of pct (treat as if < 20%). The SECOND
    # post-compact reading onward is trusted normally.
    is_first_post_compact_reading = compact_seen and post_compact_usage_count == 1

    if is_first_post_compact_reading:
        print(
            f"[POST-COMPACT] usage {pct:.1f}% is this session's first reading after a "
            "/compact — treat effective usage as < 20% for cleanup-gate purposes. This "
            "figure reflects one-time context-reconstruction cost (re-reading skills/"
            "files to resume working state), not accumulating budget pressure. Do NOT "
            "recommend /cleanup off this number; the gate resumes from the next reading."
        )
    elif pct >= rec_pct:
        print(
            f"[CLEANUP-GATE] usage {pct:.1f}% >= {rec_pct}% — RECOMMEND /cleanup at this "
            "turn's wrap-up via AskUserQuestion: include a Recommended cleanup option in "
            "any turn-final ask (any ask shape — commit/next-item asks included), or "
            "compose a standalone AskUserQuestion for the cleanup decision if no other "
            "ask is happening this turn. A text-only mention in the report ('let me know "
            "if you want /cleanup') is NOT sufficient — it is a decision left as prose "
            "and must be asked (see next/ask-gates.md Step 0.4). Skip only if cleanup "
            "already ran this session or the user declined it."
        )
except Exception:
    sys.exit(0)
PYEOF
exit 0
