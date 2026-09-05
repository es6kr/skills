# Context Measurement (on-demand / "pull" & injected / "push")

Provides on-demand ("pull") and injected ("push") context-window usage measurement across Claude Code and Antigravity (Gemini).

- `resources/context-usage-now.sh` (pull): run any time mid-turn or on a Stop re-feed for fresh context readings.
- `resources/context-usage-inject.sh` (push): registered as the `UserPromptSubmit` hook — injects one context reading per user prompt.

Use before any context-threshold decision: a ralph-loop completion promise ("context > N%"), a `/cleanup` trigger, or context-gate pacing.

## Command

```bash
bash skills/session/resources/context-usage-now.sh [transcript_path]
```

- `transcript_path` = the `Transcript:` value injected at session start, or path to `transcript.jsonl`.
- Output: `Context usage: ~Xk / Yk tokens (Z%)` plus any `[CONTEXT-STALE]` / `[CLEANUP-GATE]` lines.
- Automatically handles:
  - **Claude Code**: reads last usage-bearing assistant message (`input_tokens + cache_creation + cache_read`) and resets on `compact_boundary`.
  - **Antigravity (Gemini)**: detects `transcript.jsonl` format, identifies `<CONTEXT_SUMMARY>` compaction boundaries, prunes pre-compact turns, and computes live active tokens accurately against the 1M window.
  - **Windows / Git Bash**: normalizes `/c/...` paths to `C:/...` before probing Python.

## Rule: measure fresh before any context-threshold decision (HARD STOP)

Before acting on ANY context-threshold gate — a ralph-loop completion promise ("context > N%"), a `/cleanup` trigger, context-gate pacing — run `context-usage-now.sh` for a fresh reading. Never:

- **estimate** the percentage ("~52% based on the large turn since"),
- reuse a **stale** injected figure (one carrying `[CONTEXT-STALE]`, or from a prior turn / before a compaction),
- treat "the transcript grew" or "that was a big turn" as a measurement.

| # | Don't | Do |
|---|-------|-----|
| 1 | Output a ralph-loop promise ("context > 50%") from an estimate or a stale/aged injected figure | Run `context-usage-now.sh`; output the promise only if the **fresh** figure clears the threshold |
| 2 | Trigger `/cleanup` on a stale/aged reading (or one flagged `[CONTEXT-STALE]`) | Re-measure with `context-usage-now.sh` first; act on the fresh figure |
| 3 | Conclude "no way to measure context here" on a Stop re-feed (which carries no injected reading) | The pull path always exists — run `context-usage-now.sh` |
| 4 | Right after a `/compact` or `<CONTEXT_SUMMARY>`, trust a stale pre-compact figure | Immediately after a compact, assume the floor (below) and re-measure with the pull path |

## Post-compact floor heuristic (HARD STOP)

**Immediately after a `/compact` or `<CONTEXT_SUMMARY>` boundary, treat context as `< 20%` until `context-usage-now.sh` proves otherwise.** The injected reading on the first turn(s) after a compact still reflects the *pre-compact* window (the old summary + re-injected always-on context, not yet compressed) and is stale-**high**. This floor is a safe default before measurement to prevent premature cleanup triggers or premature ralph-loop terminations.

## Files

- `resources/context-usage-now.sh` — on-demand pull script (invoke directly, not a registered hook)
- `resources/context-usage-inject.sh` — UserPromptSubmit push hook (registered in `settings.json` / `hooks.json`)
