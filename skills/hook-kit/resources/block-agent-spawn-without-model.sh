#!/usr/bin/env bash
# PreToolUse:Agent (and Task) — three independent gates on subagent spawns:
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

# --- Gate C: high-tier model needs explicit user approval -------------------
# Gate A only fires when `model` is ABSENT, so it says nothing about whether the
# user agreed to the expensive tier that was explicitly requested. Choosing WHAT
# work to do (a next-action option) and approving WHICH TIER runs it are two
# separate axes; collapsing them is what caused an unapproved fable spawn after
# the user merely picked a "Delegate to Fable" work item.
#
# Contract:
#   BLOCK when model is opus/fable AND neither approval signal is present:
#     - the prompt carries [tier-approved] (documented explicit approval), or
#     - an AskUserQuestion tool_use appears in the current turn (the user was
#       actually consulted before this spawn)
case "$MODEL" in
  opus|fable)
    TIER_OK=0
    printf '%s' "$PROMPT" | grep -qF '[tier-approved]' && TIER_OK=1

    if [[ "$TIER_OK" -eq 0 ]]; then
      TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
      if [[ -n "$TRANSCRIPT" && -f "$TRANSCRIPT" ]]; then
        TIER_OK=$(python3 - "$TRANSCRIPT" <<'PYEOF' 2>/dev/null
import json, sys

STUB_MARKER = "is already loaded above; instructions unchanged."
entries = []
with open(sys.argv[1], encoding="utf-8", errors="ignore") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            continue

# Current turn starts at the most recent genuine user prompt (role=user with
# string content). An AskUserQuestion ANSWER comes back as a tool_result (list
# content), so it does not reset the window — the ask itself stays visible.
turn_start = 0
for i in range(len(entries) - 1, -1, -1):
    msg = entries[i].get("message") or {}
    content = msg.get("content")
    if msg.get("role") == "user" and isinstance(content, str):
        if STUB_MARKER in content:
            continue
        turn_start = i
        break

for ent in entries[turn_start:]:
    c = (ent.get("message") or {}).get("content")
    if not isinstance(c, list):
        continue
    for b in c:
        if isinstance(b, dict) and b.get("type") == "tool_use" \
           and b.get("name") == "AskUserQuestion":
            print("1")
            sys.exit(0)
print("0")
PYEOF
)
      fi
      TIER_OK="${TIER_OK:-0}"
    fi

    if [[ "$TIER_OK" != "1" ]]; then
      cat >&2 <<EOF
[hook:block-agent-spawn-without-model] BLOCKED (exit 2) — high-tier model gate

This spawn requests model "$MODEL", a high-cost tier, with no sign that the
user approved that tier for this spawn.

Picking a work item is NOT tier approval. "Delegate to Fable" as a next-action
option says which task to run — not that an expensive model may be spawned for
it without asking.

Pick one before retrying:
  - Ask the user first (AskUserQuestion naming the tier and why it is needed),
    then spawn in that same turn
  - The user already approved this tier explicitly → add [tier-approved] to the
    prompt with a one-line pointer to where they approved it
  - The task does not actually need this tier → use sonnet (or drop \`model\`
    and let Gate A inject the sonnet default)
EOF
      exit 2
    fi
    ;;
esac

# --- Gate A: model (auto-inject sonnet, do not block) -----------------------
if [[ -z "$MODEL" && "$SUBAGENT" != "fork" ]] && ! printf '%s' "$PROMPT" | grep -qF '[model-inherit-ok]'; then
  # updatedInput REPLACES the tool input wholesale — it is not merged by the
  # harness. Emitting a bare `{ model: "sonnet" }` therefore drops description /
  # prompt / subagent_type and the spawn dies on schema validation
  # ("The required parameter `description` is missing"), which is a hard failure
  # for every model-less spawn rather than the intended cheap default.
  # So echo the caller's own tool_input back with only `model` added.
  printf '%s' "$INPUT" | jq '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "allow",
      permissionDecisionReason: "No model specified — injected default \"sonnet\" instead of inheriting the parent (expensive) tier. Add [model-inherit-ok] to the prompt or set model explicitly to opt out.",
      updatedInput: (.tool_input + { model: "sonnet" })
    }
  }'
  exit 0
fi

exit 0
