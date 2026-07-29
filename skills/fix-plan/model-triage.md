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
- Marker `[BLOCKED:P<N>:selfable]` — the block reason is "awaiting the target model", so any session running that model may execute them; other sessions skip
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

## Discovery Procedure

1. **Scan** every tracker section outside the dedicated one (priority work, TODO, hold/deferred, plan drafts, carry-over) — title-level scan first, entry-level read only for ambiguous items
2. **Classify** each candidate against the category table; discard anti-fit matches
3. **Verify premises** — a candidate carried from old notes is a claim, not a fact; re-check its current state against primary sources before proposing (category III items are themselves evidence this matters)
4. **Propose** the candidate set to the user grouped by category (multi-select ask); never auto-move items
5. **Register** approved items into the dedicated section with the full schema + category tag; record declined groups inline so the next triage pass does not re-propose them

## Operating Loop

- Execute the dedicated section top-down by priority within a matching model session (autonomous loop or interactive)
- **Judge completion via [completion-criteria.md](./completion-criteria.md)** — these items are predominantly analysis/planning, so their DoD is "the named deliverable exists", not "the analyzed problem is solved". Subjects named in an item's `Why` are scope narrative, not acceptance conditions; residual axes get split into new items rather than holding the parent blocked
- On completing an item, append a dated result annotation (concretized / executed / superseded) rather than deleting the item body — the annotation chain is the audit trail
- Surfaced user decisions are recorded in the tracker + plan artifacts immediately; implementation-ready items exit the section into normal execution flow
- Stop when the section is exhausted or the session's context threshold is reached; a fully-exhausted section is the trigger for the next Discovery pass

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Fill the section with important-but-mechanical work | Importance ≠ fit. Apply the anti-fit table first |
| 2 | Treat "plan exists" as "nothing to do" | Category III: a stale plan is itself high-fit work (resync beats blind execution) |
| 3 | Auto-move candidates into the section during a scan | Discovery step 4 — user approves the set; registration follows approval |
| 4 | Start executing a candidate mid-scan | Scan → classify → propose → register → execute. Mixing phases loses the audit trail |
| 5 | Delete completed items from the section | Append result annotations; archive via the tracker's normal Completed lifecycle ([move.md](./move.md)) |
