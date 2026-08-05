#!/usr/bin/env bash
# PreToolUse:Agent (and Task) — two independent gates on subagent spawns:
#
# Gate A: an Agent/Task spawn with no explicit `model` gets "sonnet" injected
# automatically via PreToolUse hookSpecificOutput.updatedInput, instead of
# being hard-blocked — the spawn proceeds at a safe, cheap default rather than
# silently inheriting the (expensive) parent model tier.
#
# Background: in one session, 5 subagents were spawned with no `model` param and
# all inherited the parent (fable) tier; the cost-economy rule was even written
# to memory and then self-violated on the very next spawn. A memory alone did
# not hold. An earlier version of this hook hard-blocked (exit 2) instead of
# injecting — auto-injection was chosen after confirming updatedInput support
# for the Agent/Task tool via the official hooks docs (2026-08-05).
# See failed-attempts.md "agent spawn model unspecified (fable inheritance)".
#
# Contract:
#   INJECT model:"sonnet" (via updatedInput, permissionDecision:"allow") when ALL hold:
#     - tool is Agent / Task (a subagent spawn)
#     - tool_input.model is absent or empty
#     - subagent_type is NOT "fork" (fork always inherits the parent model by
#       design — a model override is ignored, so injecting is a no-op there)
#     - the prompt does NOT carry the explicit escape marker [model-inherit-ok]
#   No injection (spawn proceeds with caller's own tool_input unchanged) when:
#     - tool_input.model is already set ("haiku" | "sonnet" | "opus" | "fable")
#     - subagent_type: "fork"
#     - the prompt carries [model-inherit-ok] (documented intentional inherit)
#
# Gate B: Block spawning without an explicit `run_in_background`, forcing a
# conscious foreground/background choice instead of silently falling through
# to the tool's own background-by-default behavior.
#
# Background: a skill-scoped rule (next/SKILL.md Step 3 "Decide foreground vs
# background BEFORE spawning") existed and still got bypassed, because the
# violating spawn happened inside a *different* skill's flow (consolidate's
# Step 3.5 Internal Review dispatch) that never loads that text. A prose rule
# confined to one skill file does not generalize across every code path that
# calls Agent — this tool-level gate is the fix, mirroring Gate A's own lesson.
# See failed-attempts.md "background-agent-without-parallel-work" (2nd
# occurrence).
#
# Contract:
#   BLOCK a spawn when ALL hold:
#     - tool is Agent / Task (a subagent spawn)
#     - tool_input does NOT have a "run_in_background" key at all (present-but-
#       false still counts as an explicit, conscious choice — only *absence*
#       is the failure mode; `// empty` is unsafe here since jq's alternative
#       operator treats a `false` value as falsy too, so `has(...)` is used)
#     - the prompt does NOT carry the explicit escape marker [bg-inherit-ok]
#   Escapes (any → allow):
#     - set tool_input.run_in_background explicitly (true or false)
#     - include [bg-inherit-ok] in the prompt (documented rationale)

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL_NAME" in
  Agent|Task) ;;
  *) exit 0 ;;
esac

MODEL=$(echo "$INPUT" | jq -r '.tool_input.model // empty' 2>/dev/null)
SUBAGENT=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
PROMPT=$(echo "$INPUT" | jq -r '.tool_input.prompt // empty' 2>/dev/null)
HAS_BG=$(echo "$INPUT" | jq -r '.tool_input | has("run_in_background")' 2>/dev/null)

# --- Gate B: run_in_background (checked FIRST — still a hard block) --------
# Must run before Gate A: Gate A's injection path exits 0 immediately, so if
# it ran first on a spawn missing BOTH model and run_in_background, Gate B
# would never get evaluated and the run_in_background gate would silently
# never fire for that call.
if [[ "$HAS_BG" != "true" ]] && ! printf '%s' "$PROMPT" | grep -qF '[bg-inherit-ok]'; then
  cat >&2 <<'EOF'
[hook:block-agent-spawn-without-model] BLOCKED (exit 2) — run_in_background gate

This Agent spawn has no explicit `run_in_background` — it would fall through
to the tool's background-by-default behavior. Deciding foreground vs
background is a conscious call, not a default to inherit.

Pick one before retrying:
  - Other selected/pending/deferred work exists to drive while this agent runs
    → run_in_background: true (and actually drive that other work this turn —
      do not spawn background and then idle)
  - Nothing else is drivable right now
    → run_in_background: false (run it synchronously — you needed the result
      before continuing anyway, so there is no parallelism to gain)
  - Background is genuinely intended for a documented reason (e.g. explicit
    fire-and-forget the user asked for) → add [bg-inherit-ok] to the prompt
    with a one-line reason, or set run_in_background explicitly
EOF
  exit 2
fi

# --- Gate A: model (auto-inject sonnet, do not block) -----------------------
if [[ -z "$MODEL" && "$SUBAGENT" != "fork" ]] && ! printf '%s' "$PROMPT" | grep -qF '[model-inherit-ok]'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "allow",
      permissionDecisionReason: "No model specified — injected default \"sonnet\" instead of inheriting the parent (expensive) tier. Add [model-inherit-ok] to the prompt or set model explicitly to opt out.",
      updatedInput: { model: "sonnet" }
    }
  }'
  exit 0
fi

exit 0
