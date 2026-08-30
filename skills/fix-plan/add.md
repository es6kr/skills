# Add

New item authoring schema. Action / Why / How three-element format, length budget, deliverable separation rules.

## Item format (HARD STOP)

Every new fix_plan entry contains three required elements. Single-line action-only entries are forbidden.

```markdown
- [ ] {Action: imperative verb-form, one sentence}
  - **Why**: {motivation — purpose, background, intent in 1-2 sentences}
  - **How to apply**: {procedure / tools / verification approach}
  - {optional sub-steps, command examples, file paths}
```

### Canonical medium gate (HARD STOP — creation direction)

**Before adding a new item, determine whether this tracker is the canonical backlog or an index into an external one.** When an external tracker is canonical, an entry written only here is not a record — it is a pointer with nothing behind it, and it disappears the moment the file is regenerated or overwritten by a concurrent writer.

Detect the canonical medium from **both** signals — either alone is insufficient:

1. **Pinned header declaration** — read the file's top block (roughly the first 10 lines) before the session's first add. A tracker that delegates to an external system declares it there.
2. **Existing index lines** — count entries carrying an external reference suffix (e.g. `→ <Tracker> (<issue URL>)`). A file where such entries dominate is an index in practice, whatever the header does or does not say.

| Canonical medium | How to add |
|------------------|-----------|
| This file | Add the three-element entry normally (see below) |
| External tracker | **Create the item in the external tracker first**, then write the local entry as an index line carrying the returned URL |

| # | Don't | Do |
|---|-------|-----|
| 1 | Add `- [ ]` here and consider the item recorded, without checking whether an external tracker owns this backlog | Read the pinned header + count existing index lines first. External canonical → create there, then index here |
| 2 | Reach the file by targeted read (`offset`) or grep and therefore never see the header | The header is where delegation is declared. A targeted read that skips it also skips the rule governing the write you are about to make — under context pressure this is the normal access pattern, not an edge case |
| 3 | Defer the external write ("record locally now, sync later") | The local file is not durable against regeneration or a concurrent writer. Unsynced local-only entries are the exact loss this gate exists to prevent |
| 4 | Treat the completion-direction guard (verify the external item before flipping `[x]`) as covering this | Completion and creation are separate directions. Guarding only completion leaves every new item unprotected |

### Why each element is required

| Element | Purpose | What breaks if omitted |
|---------|---------|------------------------|
| **Action** | The work itself, in imperative form | Reader has no clue what to do |
| **Why** | Information transfer to future sessions | Future session asks the user — context decays between sessions |
| **How to apply** | Concrete procedure / tools / verification | Future session has to re-derive the approach |

### Why is mandatory — future-session test

fix_plan is a **session-to-session information transfer medium**. The context in the author's head right now will be gone in the next session. Action-only entries force future sessions to guess context and ask the user.

| # | Don't | Do |
|---|-------|-----|
| 1 | `- [ ] Register SSH deploy key → push → trigger downstream sync` (action chain only) | `- [ ] Register SSH deploy key on GitHub` <br> `- **Why**: downstream GitOps tool needs a deploy key to fetch the repo over git+ssh` <br> `- **How to apply**: ed25519 keypair → public to repo Settings/Deploy keys → private as downstream Secret` |
| 2 | `- [ ] Change identity provider settings` (target ambiguous) | `- [ ] Change identity provider's invalidation flow` <br> `- **Why**: OIDC logout then redirect bounces back to sign-in (regression)` <br> `- **How to apply**: IaC manifest → plan → apply` |
| 3 | `- [ ] X migration (see plan doc)` (plan doc reference only) | `- [ ] X migration` <br> `- **Why**: {core motivation, 1-2 sentences}` <br> `- **How to apply**: {core procedure summary}` <br> `- See: docs/generated/plan-X.md for the full spec` |
| 4 | `- [ ] step → next step → final step` (chain only, no Why) | Split each step into a separate item OR keep one main item + Why + sub-bullet steps |

### Self-check before adding

1. **Action**: clear imperative verb-form, one sentence?
2. **Why**: 1-2 sentences explaining the motivation?
3. **How to apply**: core procedure / tools / commands?
4. **Future-session test**: "Can a future session proceed from this entry alone without asking the user?" — If no, the entry is information-incomplete
5. **Canonical medium**: did you confirm, from the pinned header **and** the existing index-line count, whether an external tracker owns this backlog? If it does, was the item created there first and is this entry carrying its URL? — A local-only entry under an external canonical medium is not a record

## Length budget — verbose body forbidden (HARD STOP)

fix_plan item body content = Action + Why + How (summary) + artefact reference + external link. Maximum **5-7 lines** per item. Verbose content goes in separate artefacts.

### What does NOT belong inline

- Full diagnostic results
- Reproduction evidence tables
- Fix-option matrix (A / B / C / D trade-off)
- Trade-off discussion
- Related-context lists (4 or more items)
- Multi-step checklists (5 or more)

### Deliverable separation matrix

| Content kind | Medium | Location |
|--------------|--------|----------|
| Item identification (Action one-line) | **fix_plan body** | `- [ ] ...` |
| Why 1-2 sentences | **fix_plan body** | sub-bullet |
| How to apply summary (≤ 5 steps) | **fix_plan body** | sub-bullet |
| Artefact path (research / plan) | **fix_plan body** | 1-line sub-bullet |
| Issue / PR / comment link | **fix_plan body** | 1-line sub-bullet |
| Decision record (one-line) | **fix_plan body** | 1-line sub-bullet |
| Symptom detail / root-cause flow / reproduction table | **research artefact** | `docs/generated/research-<slug>.md` or `.ralph/docs/generated/research-<slug>.md` |
| Fix-option matrix / trade-offs / Test Plan / implementation procedure | **plan artefact** | `docs/generated/plan-<slug>.md` |
| Related-context list (4 or more items) | **inside the research/plan artefact** | same as above |
| Multi-step checklist (5 or more items) | **checklist artefact** | `docs/generated/checklist-<slug>.md` |
| Progress / status updates for an item that references a plan artefact | **linked plan artefact — its `## Progress Checklist` section** (create the section if missing) | inside the referenced `plan-<slug>.md` |
| Open action items (the referenced plan's remaining `[ ]` next-actions) | **fix_plan body — as `- [ ]` sub-checkboxes** | surface the immediate next-phase open items under the item; deeper phases stay pointer-only (keep the length budget). Distinct from "progress/status updates" above: what remains *to do* stays visible/trackable in the tracker, while status narrative goes to the plan |

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Embed diagnostic / reproduction / option matrix inline in the fix_plan body | Author `research-<slug>.md` + `plan-<slug>.md` → fix_plan body has the path only, one line |
| 2 | List 4 or more related-context items as sub-bullets in the fix_plan body | Move to a "Related context" section inside the research / plan artefact. fix_plan doesn't mention them |
| 3 | Write "Decision record" / "User decision" as a paragraph in the body | One-line sub-bullet: `- **User decision (YYYY-MM-DD)**: Option D — short rationale` |
| 4 | Allow a fix_plan body item to exceed 10 lines | Cap at 5-7 lines. Anything over → split into artefacts |
| 5 | Include the A/B/C/D comparison table in fix_plan | Move to `plan-<slug>.md` "Trade-offs" section |
| 6 | Relocate item detail into a NEW artefact without Reading the research/plan artefacts the item already references | Read each referenced artefact first — progress/status content routes into the plan's `## Progress Checklist` (create the section if missing); create a new artefact only for content with no owning research/plan doc |
| 7 | Reduce an in-progress plan (one that has open `[ ]` Progress-Checklist items) to a prose-only pointer with zero checkboxes in the tracker item | Surface the immediate next-phase open items as `- [ ]` sub-checkboxes under the tracker item (within the length budget); keep deeper phases as a pointer to the plan's `## Progress Checklist`. A tracker item for in-progress work must stay actionable — the "slim pointer" rule governs status narrative, not the open action list |

### Self-check before saving an entry

1. Is the body 5-7 lines or fewer? If over, split into artefacts
2. Does the entry contain diagnostics / reproduction / option matrix / related context? If yes, move to research/plan artefacts
3. Is each artefact path expressed as a one-line sub-bullet?
4. Are decision links one line each?
5. Does the item already reference a research/plan artefact? Read it BEFORE relocating any content — progress/status updates belong in that plan's `## Progress Checklist` (create it if missing), not in a new standalone file
6. Does the referenced plan have open `[ ]` Progress-Checklist items? If yes, did you surface the immediate next-actions as `- [ ]` sub-checkboxes in the tracker item, rather than leaving a prose-only pointer?

### Example — Bad (verbose)

```markdown
- [ ] SSO re-login auto-logout fix
  - **Why**: …30 lines of diagnostics / reproduction evidence / option matrix / related context, four items…
```

### Example — Good (split)

```markdown
- [ ] SSO re-login anonymous-logout guard
  - **Why**: Logout → immediate re-login triggers a first-cycle auto-logout. Affects all environments / apps / accounts
  - **Reproduction env**: dev-cluster / sample app / admin role
  - **Decision (2026-05-21)**: Option D (proxy + login route) — single PR
  - **Artefacts**: `docs/generated/research-sso-relogin-anonymous.md` + `plan-sso-relogin-anonymous-guard.md`
  - **Issue**: #255 comment (link)
```

## See also

- [format.md](./format.md) — section structure and markers
- [priority.md](./priority.md) — `[BLOCKED:P0-P3:reason]` annotation when an item is blocked
- [move.md](./move.md) — how `[x]` entries get summarised into Completed
- [upsert.md](./upsert.md) — dup-check the tracker before running this topic's schema; this file is upsert's fallback path for genuinely new items
