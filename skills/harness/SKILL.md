---
name: harness
description: AI harness for stable LLM workflows. Topics — pipeline (clarify → ground → plan → generate → verify, dispatches to code-workflow) [pipeline.md], guardrails (denylist + scope + conditional-reject, self-contained for openclaw headless) [guardrails.md], recovery (fail-analyze → adapt → fallback, self-contained) [recovery.md]. Use when enforcing stable AI agent workflows, applying guardrails to autonomous execution, or recovering from verification failures. "harness", "AI harness", "pipeline guardrails", "fail recovery", "workflow stability", "agent harness" triggers
metadata:
  author: es6kr
  version: "0.0.0" # x-release-please-version
depends-on:
  - code-workflow
---

# Harness

Meta-layer that enforces stable, trustworthy LLM workflows. Composes three concerns into one cohesive harness:

1. **Pipeline** — enforce a `clarify → ground → plan → generate → verify` sequence so the agent's output is checked against intent and ground truth before commitment.
2. **Guardrails** — block destructive operations, bound work to the user's stated scope, and reject ambiguous instructions with a clarifying question instead of guessing.
3. **Recovery** — when verification fails, analyze the cause, adapt the approach, retry within a bounded budget, then escalate to the human.

Architecture is hybrid: `pipeline` delegates to `code-workflow` (DRY — no body duplication), while `guardrails` and `recovery` are self-contained so the harness still operates in headless / autonomous runtimes where the full skill set may not be present.

## Topic Dispatch

**When this skill is invoked with a topic specifier (e.g., `/harness pipeline` or `Skill("harness", "pipeline")`), load and follow only the matching topic file (`pipeline.md`). Do not echo the Topics table or summarize other topics in the response.** The Topics table below is an index for invocations without a topic specifier — it is not user-facing output when a topic is named.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| pipeline | Five-stage workflow gate (clarify → ground → plan → generate → verify) — dispatches to code-workflow for plan/research/implement | [pipeline.md](./pipeline.md) |
| guardrails | Pre-execution denylist + scope check + conditional-reject; self-contained for headless runtimes | [guardrails.md](./guardrails.md) |
| recovery | Bounded fail-analyze → adapt → retry → fallback; self-contained | [recovery.md](./recovery.md) |

## Topic Dependencies

```text
harness (entry — pipeline / guardrails / recovery dispatch)
  ├─→ pipeline (clarify → ground → plan → generate → verify)
  │     └─→ code-workflow/steps     (Skill call — plan + research + branch)
  │     └─→ code-workflow/implement (Skill call — TDD cycle + build + commit)
  ├─→ guardrails (self-contained — denylist + scope + conditional-reject)
  └─→ recovery   (self-contained — fail-analyze + adapt + fallback)
```

- **pipeline**: composed flow; calls `code-workflow` topics via `Skill(...)` rather than copying their bodies (DRY)
- **guardrails**: self-contained so the harness can guard execution when running detached from the larger skill set (e.g., headless `exec` / `approvals` runtimes)
- **recovery**: self-contained for the same reason; references `fix` (5-Why) and `tdd/run` (verification-failure handling) patterns by inspiration but does not declare them as runtime dependencies

## Quick Reference

### Pipeline

```text
clarify  → ask for missing intent (no guessing on ambiguous user input)
ground   → read source-of-truth (code, docs, API) before planning
plan     → produce reviewable plan deliverable
generate → execute the plan
verify   → check output against intent + ground truth
```

The harness owns `clarify`, `ground`, and `verify` orchestration; the `plan` and `generate` stages are dispatched via the abstract `--pipeline=<skill>:<topic>` contract (defaults to `code-workflow:steps` and `code-workflow:implement`).

See [detailed guide](./pipeline.md).

### Guardrails

```text
denylist            → reject destructive commands without explicit user authorization
scope check         → bound work to the user's stated request; refuse drift
conditional reject  → on ambiguous instructions, ask instead of guess
```

Self-contained — no runtime dependency on `hook-kit` or `ask-user`. Richer guard machinery can be plugged in via `--guard=<skill>:<topic>` when available.

See [detailed guide](./guardrails.md).

### Recovery

```text
fail-analyze → identify failure class (input / logic / environment)
adapt        → adjust the approach (re-plan / change tool / shrink scope)
retry        → bounded attempts (default 2)
fallback     → escalate to the user with the failure summary
```

See [detailed guide](./recovery.md).

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `denylist` | conservative built-in (destructive shell + git operations) | Command patterns requiring explicit user authorization before execution |
| `scope-source` | `{user-request}` | Origin of the work-scope boundary used by the guardrails scope check |
| `retry-budget` | `2` | Maximum retries before escalating to fallback |
| `--pipeline=<skill>:<topic>` | `code-workflow:steps` + `code-workflow:implement` | Receiver for the plan / generate stages |
| `--guard=<skill>:<topic>` | (none — internal denylist) | Optional richer guard machinery |
| `--recovery=<skill>:<topic>` | (none — internal analyzer) | Optional richer recovery machinery |

All receiver flags follow the abstract dispatch pattern (`skill-kit/portability` Rule B). Default values keep the harness operational without any external skill installed.

## When to Use

- Wrapping an autonomous LLM agent (headless `exec`, scripted runs) where you cannot inspect each step yourself
- Replaying a workflow that historically drifted into out-of-scope changes
- Establishing a denylist around destructive operations for a coding agent
- Treating verification failure as a recoverable state (analyze + adapt + bounded retry) instead of a hard stop

## Related

- `code-workflow` — primary pipeline receiver; carries the plan / generate stages
- `skill-kit/portability` — abstract dispatch contract followed by the receiver options above
- `fix` — recovery topic borrows the 5-Why analysis pattern without runtime dependency
- `tdd/run` — recovery references the verification-failure handling pattern

## See Also

- Phase 2 (not yet bundled): consolidate + github-flow + web-browser
