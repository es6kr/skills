# Pipeline

Five-stage workflow gate that enforces a deliberate sequence between user intent and committed output. Stages 1, 2, and 5 are owned by the harness; stages 3 and 4 are dispatched.

```text
clarify  →  ground  →  plan  →  generate  →  verify
(harness)  (harness)  (dispatch)  (dispatch)  (harness)
```

## When to Use

- The agent is about to act on a fresh user request
- A previous run drifted away from intent (e.g., wrote past the requested scope) — the pipeline gives the next attempt a structural reset
- The runtime is autonomous (headless `exec`, scripted) and self-review of each step is the only review

## Inputs

| Input | Form | Notes |
|-------|------|-------|
| User request | natural-language string | Source of truth for `clarify` and the scope boundary for `verify` |
| `--pipeline=<skill>:<topic>` | abstract dispatch contract | Default `code-workflow:steps` + `code-workflow:implement`. Caller may override |
| `--ground-source=<glob\|skill>` | optional | Where to read ground truth in stage 2 (default: workspace files matching the request) |

## Stages

### Stage 1 — Clarify (harness-owned)

Resolve missing intent BEFORE doing any work. Ambiguous verbs, undefined subjects, and unstated success criteria are all clarify triggers.

| # | Don't | Do |
|---|-------|-----|
| 1 | Guess the most likely interpretation and silently proceed | Surface the ambiguity to the user; ask one clarifying question per axis |
| 2 | Bundle clarifications into a single mega-question | One axis per question; preserves the user's ability to answer each independently |
| 3 | Treat the previous turn's interpretation as authoritative when this turn's wording is new | The new wording can flip intent — re-clarify when the verb or subject changes |

**Self-check** (before exiting Stage 1):
1. Is there exactly one defensible interpretation of the request? (If multiple, ask)
2. Are the success criteria stated in checkable terms? (If not, ask)
3. Is the scope boundary explicit? (If not, ask — this fuels the `verify` stage)

### Stage 2 — Ground (harness-owned)

Read the source of truth before planning. Common ground sources: workspace code, framework docs, API responses, existing config files.

The ground stage prevents the most expensive failure mode of plan-and-generate: the plan reads plausible but stale knowledge instead of the actual codebase / API surface that exists right now.

| # | Don't | Do |
|---|-------|-----|
| 1 | Plan from memory of "how libraries usually work" | Read the actual import in the workspace; check the actual API response shape |
| 2 | Treat training-data knowledge as ground truth for a third-party library | Fetch current docs (the library's site, or a local docs cache); training data is a cutoff snapshot |
| 3 | Skip ground when the request is "small" | Small requests in unfamiliar code are exactly where stale assumptions bite |

**Self-check** (before exiting Stage 2):
1. Did you read the file you are about to modify (or a representative sample)? (If no, read first)
2. For external dependencies, do you have current-version evidence (docs, type definitions, response samples)? (If no, fetch)
3. Are the ground findings written down so the `plan` stage can cite them? (If no, write a short ground note)

### Stage 3 — Plan (dispatched)

Hand off to `--pipeline=<skill>:<topic>` (default `code-workflow:steps`). The plan deliverable is a markdown plan with: approach, file targets, code snippets, and trade-offs.

The harness does not duplicate the plan procedure body; it relies on the receiver's procedure and only enforces that a plan deliverable is produced before moving on.

**Gate** (the harness checks before allowing Stage 4):
1. Plan deliverable exists at a known path (a markdown file the receiver designated)
2. The plan references the ground notes from Stage 2 (cites at least one ground finding)
3. The plan declares a `Verification` section that the harness can read in Stage 5

### Stage 4 — Generate (dispatched)

Hand off to `--pipeline=<skill>:<topic>` (default `code-workflow:implement`). Same delegation pattern as Stage 3 — the harness does not implement TDD or commit logic; it relies on the receiver and enforces the gate.

**Gate** (the harness checks before allowing Stage 5):
1. The receiver reports completion (returns control to the harness)
2. Tests or equivalent runtime checks declared in the plan have been executed (receiver responsibility — harness checks the report, not the run)
3. No out-of-scope file modifications relative to the plan's file targets (harness reads `git status` or equivalent)

### Stage 5 — Verify (harness-owned)

Check the actual output against the original request and the ground notes. This stage is owned by the harness because the receiver is unlikely to review its own output critically.

| Check | How |
|-------|-----|
| Intent satisfied | Re-read the user request; restate the verification criterion in one sentence; compare with the output |
| Scope respected | Diff the workspace against the plan's `file targets` — flag any file outside the plan |
| Ground assumptions still hold | Re-spot-check the ground findings against the modified code |
| User-facing artifacts present | If the request implied a deliverable (PR body, summary, screenshot), check it exists |

**Outcomes**:

| Verify result | Next |
|---------------|------|
| ✅ pass | Report completion to the user; harness exits |
| ❌ fail | Dispatch to `recovery` topic — do not silently retry |

## Dispatch contract

The `--pipeline=<skill>:<topic>` flag follows the abstract dispatch pattern in `skill-kit/portability` (Rule B). The harness does not embed a vendor-specific receiver name; the caller decides which skill provides the plan / generate stages.

```bash
# Default (uses code-workflow)
/harness pipeline "Refactor the auth middleware"

# Custom plan receiver
/harness pipeline "Refactor the auth middleware" --pipeline=my-org-flow:design

# Custom plan + generate (single receiver covers both)
/harness pipeline "Refactor the auth middleware" --pipeline=my-org-flow:full
```

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Skip `clarify` because "the request is short" | Short requests often omit subject/verb/scope; clarify the missing axes |
| 2 | Plan from training-data memory of a library | Read the actual import + current docs in `ground` first |
| 3 | Copy the receiver's plan / generate procedure into this topic | Stay thin — dispatch via `--pipeline=<skill>:<topic>` |
| 4 | Treat a "tests pass" report from `generate` as proof of correctness | `verify` separately checks intent + scope, not just runtime success |
| 5 | Hide `verify` failures by re-running `generate` immediately | Verify failure dispatches to `recovery` (analyze first, retry second) |

## Self-check (HARD STOP — before exiting the pipeline)

1. Did all five stages run, in order? (Skipping is forbidden)
2. Stage 1 ambiguity — was it resolved with a question, not a guess?
3. Stage 2 ground — were findings written down and cited in the plan?
4. Stages 3-4 — was the work dispatched via the abstract `--pipeline=<skill>:<topic>` flag (no hardcoded receiver)?
5. Stage 5 verify — did you compare actual output against the original request, not just receiver-reported success?

## Output

| Output | Always | Notes |
|--------|--------|-------|
| Clarify resolutions (1-3 lines per axis) | ✅ | Quoted in the report so the user can audit interpretation |
| Ground notes (compact bullets) | ✅ | Cited in the plan |
| Plan deliverable | ✅ | Owned by the plan receiver |
| Generated changes (code + tests) | ✅ | Owned by the generate receiver |
| Verification report (pass/fail + diff scope) | ✅ | Harness-owned |
| Recovery dispatch trace | only on fail | See `recovery.md` |

## Related

- `code-workflow/steps` — default plan receiver
- `code-workflow/implement` — default generate receiver
- `guardrails` — runs as a cross-cutting check on every dispatched stage (denylist + scope + conditional-reject)
- `recovery` — dispatched on Stage 5 fail
- `skill-kit/portability` — abstract dispatch contract for the `--pipeline` flag
