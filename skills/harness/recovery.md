# Recovery

Bounded recovery loop dispatched when `pipeline` Stage 5 (verify) fails or when `guardrails` blocks execution mid-run. Self-contained — the harness ships a minimum analyzer so it can recover in headless runtimes where richer recovery skills (`fix`, `tdd/run`) may be absent.

```text
fail-analyze  →  adapt  →  retry  →  fallback
```

## When to Use

- `pipeline` Stage 5 (verify) reports a fail
- `guardrails` blocks an operation and the agent needs a deliberate next move (retry with different inputs, or escalate)
- An autonomous run produced a verification failure and the runtime cannot surface a human in the loop

## Inputs

| Input | Form | Notes |
|-------|------|-------|
| Failure context | structured (stage, observed result, expected result) | Comes from `pipeline.verify` or `guardrails.block` |
| `--retry-budget=N` | integer | Max retries before escalation; default `2` |
| `--recovery=<skill>:<topic>` | abstract dispatch contract | Optional richer recovery receiver (e.g., a 5-Why analyzer) |

## Stages

### Stage 1 — Fail-analyze

Classify the failure before deciding what to change. Three classes cover most cases:

| Class | Signal | Typical adapt |
|-------|--------|---------------|
| Input | Failure is about what the user asked for (intent mismatch, scope drift) | Re-clarify; do not re-execute with the same intent |
| Logic | Failure is about how the implementation works (test fail, wrong branch hit) | Re-plan or change tool; the spec is right, the build is wrong |
| Environment | Failure is about the runtime (missing dependency, version mismatch, permission) | Fix the environment; the spec and build are right |

The minimum analyzer asks two questions:

1. **What changed between the expected and observed result?** (one sentence)
2. **Which class explains the gap?** (input / logic / environment)

A richer analyzer is plugged in via `--recovery=<skill>:<topic>` — for example, a 5-Why receiver that drills past the first answer. The built-in 2-question version is sufficient for headless recovery.

### Stage 2 — Adapt

Adjust the approach based on the failure class:

| Class | Adapt patterns |
|-------|----------------|
| Input | Re-run `pipeline.clarify` with the failure as a new input; re-derive the intent |
| Logic | Re-run `pipeline.plan` with the ground notes augmented by the failure observation; keep the intent, change the implementation strategy |
| Environment | Apply the environment fix (install, version-pin, permission); do not change the plan |

The adapt choice is recorded so the retry attempt has clear ground for comparison.

### Stage 3 — Retry (bounded)

Re-run the affected pipeline stages with the adapted approach. The retry budget is bounded (default `2`) to prevent infinite loops.

| # | Don't | Do |
|---|-------|-----|
| 1 | Retry with the same inputs that just failed | The adapt step must have changed something; otherwise skip to `fallback` |
| 2 | Increase the retry budget mid-loop "to give it one more shot" | The budget is set at run start; mid-loop expansion masks a real fallback condition |
| 3 | Reset the retry counter when the failure class changes | The counter is across all classes; a new class is still a retry against the same budget |

After each retry, run `pipeline.verify` again. Pass → exit recovery. Fail → next attempt or fallback.

### Stage 4 — Fallback

When the retry budget is exhausted (or the failure class is "input" and clarification reveals the original request was unworkable), escalate to the user.

The fallback report contains:

| Field | Content |
|-------|---------|
| Failure summary | One sentence — what was attempted, what failed |
| Failure class | input / logic / environment |
| Attempts | Per-retry adapt choice + verify outcome |
| Suggested next step | What the harness would do if the budget were extended (re-plan / change tool / human review) |

The fallback does not silently abandon the request. It returns control to the human with enough context to decide the next move.

## Dispatch — richer recovery machinery

When a richer recovery skill is available, plug it in via `--recovery=<skill>:<topic>`. The receiver is consulted instead of the minimum analyzer for Stage 1; Stages 2-4 are still owned by the harness.

```bash
# Default (built-in 2-question analyzer)
/harness pipeline "Refactor auth"

# Plug in a 5-Why receiver
/harness pipeline "Refactor auth" --recovery=fix:step1
```

The dispatch follows the abstract contract in `skill-kit/portability` (Rule B). The receiver name is not embedded in this topic.

## Composition with the pipeline

```text
pipeline.verify  →  ❌ fail  →  recovery.fail-analyze  →  recovery.adapt  →  recovery.retry  →  pipeline.<stage>
                                                                                    │
                                                                                    └─→  recovery.fallback (on budget exhaustion)
```

The retry re-enters the pipeline at the stage that maps to the failure class:

| Failure class | Re-enter pipeline at |
|---------------|----------------------|
| Input | `clarify` (Stage 1) |
| Logic | `plan` (Stage 3) |
| Environment | `generate` (Stage 4) after the environment fix |

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Retry without explaining what changed | The adapt step must produce a one-line diff statement that the retry can be compared against |
| 2 | Treat every failure as a logic failure | Failure class matters — input failures need re-clarify, environment failures need an environment fix |
| 3 | Run the same retry budget for every failure class | Budget is shared across classes; once exhausted, escalate to fallback regardless of class |
| 4 | Hardcode a receiver name in this topic body | Use the abstract `--recovery=<skill>:<topic>` dispatch |
| 5 | Silently retry inside a single user turn until something works | The user should see each retry attempt or at least the final fallback report — silent retries hide real problems |

## Self-check (HARD STOP — at every recovery entry)

1. Did `pipeline.verify` (or `guardrails.block`) produce a structured failure context? (If no, re-run with diagnostic output before entering recovery)
2. Did `fail-analyze` produce a failure class? (If unsure, default to `logic` — most diagnosable)
3. Did `adapt` produce a one-line diff statement? (If no, retry is pointless — escalate)
4. Is the retry budget remaining? (If no, go straight to `fallback`)
5. After retry, did `pipeline.verify` re-run? (If skipped, the loop is broken)

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--retry-budget=N` | `2` | Maximum retry attempts before fallback escalation |
| `--recovery=<skill>:<topic>` | (none — built-in 2-question analyzer) | Richer fail-analyze receiver |
| `--fallback=<channel>` | runtime-default | How the fallback report is surfaced (chat, log file, ticket system) |

## Output

| Output | When |
|--------|------|
| Failure class label | After Stage 1 |
| Adapt one-line statement | After Stage 2 (per attempt) |
| Retry attempt trace | During Stage 3 |
| Fallback report | On budget exhaustion or unrecoverable failure class |
| Recovery success report | When a retry passes `pipeline.verify` |

## Related

- `pipeline` — dispatches to recovery on Stage 5 fail
- `guardrails` — dispatches to recovery when a block forces a deliberate next move
- `skill-kit/portability` — abstract dispatch contract for the `--recovery` flag
- `fix` (external pattern) — 5-Why analyzer inspiration; not a runtime dependency
- `tdd/run` (external pattern) — verification-failure handling inspiration; not a runtime dependency
