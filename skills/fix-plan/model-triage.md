# Model Triage

Route backlog items to the model tier best suited to them. High-capability (deep-reasoning) model windows are scarce and expensive — this topic defines (a) which backlog items qualify, (b) how to discover candidates across the tracker, and (c) how to operate a dedicated tracker section for them.

## When to Use

- A high-capability model window opens (promotion period, dedicated budget) and you need to fill it with the highest-leverage work
- "Which tasks deserve the strong model?" / "model triage" / "complex-task triage"
- Periodic re-triage when the dedicated section is exhausted
- **The default invocation resolves to the `deep` role profile** (see SKILL.md "Role-based execution") — a `deep` session's no-arg `/fix-plan` runs this topic's re-discovery pass instead of the mechanical move/format steps; `pm` sessions run the bookkeeping pipeline and skip this topic

## Section Convention

Maintain a dedicated tracker section named `## <Model> Target Tasks` (e.g., a top-tier model's name). Items follow the same authoring schema as [add.md](./add.md) (Action / Why / How) plus:

- **Draft/Plan** line pointing to existing plan artifacts (or `(none — greenfield)`)
- Marker `[BLOCKED:P<N>:external]` — the block reason is "awaiting the target model" (a true external dependency per [priority.md](./priority.md)'s `external`/`selfable` classification: the item cannot proceed without that specific model session), so any session running that model may execute them; other sessions skip
- A category tag (see below) so future triage passes can audit fit

## Suitability Categories

| # | Category | Nature | Signal it fits |
|---|----------|--------|----------------|
| I | Greenfield architecture planning | Multi-layer (infra + app + security) alternative comparison, trade-off tables, plan authoring | No plan exists; decision axes span systems |
| II | Root-cause follow-up design | Diagnosis is DONE; the structural remedy needs design | Tracker item carries a confirmed root-cause note but no remedy plan |
| III | Stale plan ↔ reality resync | Plan documents lag the implemented reality; full re-measurement + rewrite | Plan predates merged PRs / deployments touching its scope |
| IV | Large-corpus classification | Hundreds of sections/files needing semantic classification, dedup, reconciliation | Mechanical rules fail; per-item judgment required |
| V | Executive / proposal documents | Cost models, persuasion structure, evidence synthesis | Audience is management; quality of argument matters |

### Anti-fit (exclude even if "important")

| Anti-pattern | Why excluded | Route instead |
|--------------|--------------|---------------|
| Mechanical execution (deploy, apply, click-ops) | No reasoning leverage | Any session with the required access |
| External-response-gated items | Blocked on third parties, not on thinking | Leave in place with trigger note |
| Environment-gated items (kubeconfig, VPN, host access) | Model tier irrelevant to the blocker | Session on the right machine |
| Single-file trivial edits | Cost exceeds value | Regular session |

## Discovery & Replenishment Procedure

1. **Scan via Scanner Script** — Run the automated replenishment candidate scanner:
   ```bash
   python <skill-dir>/scripts/fable_queue_replenish.py --root .
   ```
2. **Scan Tracker Sections** — Scan every tracker section outside the dedicated one (priority work, TODO, hold/deferred, plan drafts, carry-over), **plus any `impl`-promoted plan artifact awaiting audit** (see [draft.md](./draft.md) "Role ownership" — `impl` promotes drafts by default; this scan is where architecture-scale output gets picked up for `deep` review, not authored by `deep` from scratch) — title-level scan first, entry-level read only for ambiguous items
3. **Classify** each candidate against the category table; discard anti-fit matches
4. **Verify premises** — a candidate carried from old notes is a claim, not a fact; re-check its current state against primary sources before proposing (category III items are themselves evidence this matters)
5. **Propose** the candidate set to the user grouped by category (multi-select ask); never auto-move items
6. **Register** approved items into the dedicated section with the full schema + category tag; record declined groups inline so the next triage pass does not re-propose them

## Operating Loop

- Execute the dedicated section top-down by priority within a matching model session (autonomous loop or interactive)
- **Judge completion via [completion-criteria.md](./completion-criteria.md)** — these items are predominantly analysis/planning, so their DoD is "the named deliverable exists", not "the analyzed problem is solved". Subjects named in an item's `Why` are scope narrative, not acceptance conditions; residual axes get split into new items rather than holding the parent blocked
- On completing an item, append a dated result annotation (concretized / executed / superseded) rather than deleting the item body — the annotation chain is the audit trail
- Surfaced user decisions are recorded in the tracker + plan artifacts immediately; implementation-ready items exit the section into normal execution flow
- **`audit_status: approved_by_*` → implementation-queue move obligation (HARD STOP)**: When any item in `## Deep Tasks` (or any dedicated model-triage section) carries `audit_status: approved_by_opus` / `approved_by_fable_audit` / `approved_by_opus_audit`, the **audit STAGE is complete but the ITEM is not — implementation remains**. Never flip it to `[x]` and never harvest it to Completed on audit approval alone (the generic completion-criteria "deliverable exists → `[x]` + residual split" rule does NOT apply here — see [completion-criteria.md](./completion-criteria.md) cross-note). Leaving it in the dedicated section across a subsequent `move` or `fix-plan` default pass is strictly forbidden: on the very next `move`-phase execution (or `fix-plan` default run), **every such approved item MUST be relocated to the tracker's implementation-queue section (e.g. `## TODO`)** — NOT to a priority/execution section — with its full body, scope, and resume note preserved verbatim. Only the enclosing section header changes. Annotation-only (marking approved without moving) is not a valid stopping point — the move is the stage transition that hands the item to implementation.
- Stop when the section is exhausted or the session's context threshold is reached; a fully-exhausted section is the trigger for the next Discovery pass

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Fill the section with important-but-mechanical work | Importance ≠ fit. Apply the anti-fit table first |
| 2 | Treat "plan exists" as "nothing to do" | Category III: a stale plan is itself high-fit work (resync beats blind execution) |
| 3 | Auto-move candidates into the section during a scan | Discovery step 4 — user approves the set; registration follows approval |
| 4 | Start executing a candidate mid-scan | Scan → classify → propose → register → execute. Mixing phases loses the audit trail |
| 5 | Delete completed items from the section | Append result annotations; archive via the tracker's normal Completed lifecycle ([move.md](./move.md)) |
| 6 | Flip an audit-approved item to `[x]` (or harvest it to Completed) because the audit deliverable exists | Audit approval = stage transition, not item completion. Move it to the implementation-queue section (e.g. `## TODO`); `[x]` only when the implementation itself completes |
| 7 | Substitute an item's documented next-step with a broader action just because a self-authored `AskUserQuestion` got a "yes" | Execute the exact next-step the item's own note specifies. A note like "review complete — post as an issue comment, awaiting approval there" names a specific hand-off channel — implementing the fix directly is not the same action, even with fresh approval |
| 8 | Treat any `[BLOCKED:P<N>:external]` item as free for the current session to implement, once the note shows another session (e.g. a dedicated high-capability model session) already produced the analysis | A note crediting another session's completed diagnosis is not itself a signal that the item is implementation-ready. Check whether that note's own "remaining" field says "implement" or something narrower (post a comment, await a decision) — an item only becomes implementation-ready when its own documented next-step says so |
| 9 | Close a deep-session default invocation report-only because re-discovery proposed no new entries ("section not exhausted → nothing to propose") | Re-discovery and execution surfacing are separate axes. In a matching model session, surface the dedicated section's top items (Operating Loop) plus promote-ready Plan Drafts and complex-tier impl items as execution candidates for THIS session — see SKILL.md "deep-profile completion handoff" |

### Cross-session handoff boundary (HARD STOP)

An item whose note credits a **different session or role** (e.g. a dedicated deep-reasoning model session) with completed analysis often also documents that session's own intended completion channel — "post the findings as an issue comment, awaiting approval there," for example. That channel is not interchangeable with "implement the fix now."

**Self-check before executing (not just researching) such an item**:
1. Does the item's note credit a distinct session/role for the analysis? → if yes, continue
2. Does the item's own "remaining" / next-step field name a specific channel (comment, report, hand-off) rather than "implement"? → if yes, that channel is the deliverable — implementing code is a different, larger action than what was asked
3. Before taking the larger action, surface the ownership question as its own `AskUserQuestion` axis — "follow the documented channel (post as issue comment, let that session's owner decide) vs. take it over and implement directly now" — not folded into a narrower "apply the fix?" question. A "yes" to the narrower question does not carry authorization for the ownership takeover the user never saw as a distinct choice.

This generalizes the "different session owns this" principle beyond the dedicated `## <Model> Target Tasks` section to any item whose note attributes work to a session that has not yet formally handed it to normal execution flow.
