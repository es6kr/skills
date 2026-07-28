# Completion Criteria

Defines **what "done" means per item output type**, and how markers transition when the deliverable is finished. Without an explicit definition of done (DoD), completion judgment falls to ad-hoc discretion — and discretion that leans conservative produces items that stay blocked forever despite their deliverable already existing.

## When to Use

- Before flipping any tracker item to `[x]`, or deciding to leave it `[BLOCKED]`
- When an item's deliverable looks finished but some scope named in its body is still untouched
- Periodic audit: "is anything blocked that actually has nothing left to block on?"

## Core Rule: `Why` is scope narrative, `How to apply` is the deliverable

An item's body has two fields that are routinely conflated. Only one of them defines done.

| Field | Role | Defines DoD? |
|-------|------|--------------|
| **Why** | Narrative of the problem area and its motivation. Names systems, axes, and concerns the item *relates to* | **No** — it is context, not an acceptance checklist |
| **How to apply** | The concrete artifact or action the item must produce | **Yes** — this is the acceptance criterion |

Promoting every subject named in `Why` into a completion condition is the primary failure mode. A planning item whose `Why` mentions five subsystems does not require all five to be implemented — it requires the artifact named in `How to apply` to exist.

## DoD by output type

| Output type | Signal in `How to apply` | Done when | NOT required for done |
|-------------|--------------------------|-----------|----------------------|
| **Analysis / plan** | "author a plan", "review", "assess", "produce a design", "supplement the plan" | The document exists and covers the axis it claims to cover | Implementation, runtime verification, resolution of the analyzed problem |
| **Implementation** | "implement", "apply", "migrate", "wire up", "fix" | Code/config changed **and** verified by the item's own stated verification means | Downstream adoption, follow-up refactors |
| **Registration / record** | "register", "record", "file an issue", "document" | The record exists at the named destination | Any action the record describes |
| **Decision** | "decide", "choose", "settle" | The decision is made and written to a durable medium | Executing the decision |
| **External-gated** | "await", "track", "monitor" | The external party responded | Anything the responder controls |

**The discriminator is the verb in `How to apply`, not the size of the subject matter.** A plan covering a large system is still a plan.

## Marker transition

| Situation | Marker | Action |
|-----------|--------|--------|
| Deliverable per `How to apply` complete, no residual scope | `[x]` | Append dated result annotation, then move per the `move` topic |
| Deliverable complete, but a scope named in `Why` remains unaddressed | `[x]` on the parent | **Split the residual into a new item** with its own `Why` / `How to apply`. Do not hold the parent open |
| Deliverable partially written (artifact exists but incomplete on its own stated axis) | keep `[ ]` / `[BLOCKED:P*:selfable]` | Annotate what is missing; the artifact itself is the remaining work |
| Blocked on a third party | `[BLOCKED:P*:external]` | Record the trigger that unblocks it |
| Blocked on a decision only the user can make | `[BLOCKED:P*:selfable]` | Surface the decision via an ask — do not leave it as prose |

### `:selfable` never means "wait"

`:selfable` marks an item as **progressable now**. If an item carries `:selfable` and nothing external is pending, the correct action is to advance it, not to leave it parked. When a `:selfable` item cannot advance, the reason belongs in the annotation — and if that reason is a third party, the suffix should have been `:external`.

## Residual scope: split, don't hold

When the deliverable is done but part of the `Why` narrative remains untouched, holding the parent open buries the finished work and makes the tracker misreport progress. Split instead:

1. Flip the parent to `[x]` with an annotation stating exactly which axes the deliverable covered
2. Create a new item for the residual axis, with its own `How to apply` naming a concrete deliverable
3. Cross-reference the two so the lineage is traceable

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat every subject named in `Why` as an acceptance condition | Read DoD from `How to apply` only. `Why` is context |
| 2 | Hold a planning item open until the analyzed problem is actually fixed | A plan is done when the plan exists. Implementation is a separate item |
| 3 | Keep a parent `[BLOCKED]` because one sub-axis is untouched | Close the parent, split the residual into its own item |
| 4 | Leave `:selfable` items parked with no pending external input | `:selfable` = advance it now, or restate the blocker (and re-suffix to `:external` if it is one) |
| 5 | Import verification/adoption standards from implementation items into analysis items | Match the DoD to the output type in the table above |
| 6 | Decide completion silently and move on | Every transition gets a dated annotation naming the axes covered and the axes deferred |

## Self-check (before leaving any item `[BLOCKED]` or flipping it to `[x]`)

1. What does this item's **`How to apply`** name as the deliverable? Quote it.
2. Which output type does that verb map to in the DoD table?
3. Does the deliverable exist and cover its own stated axis? → If yes, the item is done regardless of untouched `Why` subjects.
4. Is there residual scope? → Split it into a new item; do not hold the parent.
5. If leaving it blocked: is the blocker a third party (`:external`) or a user decision (`:selfable` + an ask this turn)? If neither, it is not blocked — advance it.
6. Did I write a dated annotation stating which axes were covered and which were deferred?

## Visibility of the judgment

A completion judgment the user cannot see has not been communicated. When the tracking medium does not render a checklist in the interface — for example when a CLI fallback is used because the native task tool is unavailable — the item states and transitions must additionally be surfaced as readable text in the response. Tool output alone is not user-facing presentation.

## See Also

- [format.md](./format.md) — marker schema and section structure
- [priority.md](./priority.md) — `P0`-`P3` ranking and `external` / `selfable` classification
- [move.md](./move.md) — `[x]` → Completed summary lifecycle
- [model-triage.md](./model-triage.md) — dedicated target-model section operation
