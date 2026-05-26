# Post-Summary Next-Action Ask

After AI Review Summary post + Status line output, ask for the PR handling direction (merge/verify/defer). Final stage of the consolidate workflow.

Entry: `Skill("consolidate", "next ...")` or `pr.md` Workflow Step 8.

## Step 8: Post-Summary Next-Action Ask (MANDATORY — immediately after Status line)

Immediately after the Status line output, **ask the user for the PR handling direction**. Terminating without presenting options = procedural violation, **except** when the routing table below explicitly permits skipping (i.e., the only possible follow-up is "defer", so there is genuinely no actionable next step).

### Routing: next vs wip

| Situation | Skill to use | Reason |
|-----------|-------------|--------|
| Single PR consolidate completed | `Skill("next")` | "Follow-up action after task completion" pattern. single question with 2-4 options |
| Consolidating multiple PRs in sequence | `Skill("wip")` | 1 question per task for independent per-PR decisions (questions array up to 4) |
| Fewer than 1 follow-up action (no option other than defer) | Skip ask, terminate with report | Clearly no next step |

### Option composition guide (single PR — next skill)

To pass the `block-merge-without-review.sh` guard, **the merge option description must explicitly include "AI Review Summary posted (URL)"**.

| Merge 4-condition satisfaction | Recommended options (Recommended at top) |
|-------------------------------|------------------------------------------|
| 4/4 satisfied | (1) Squash merge — AI Review Summary posted (URL) (2) Apply Minor then merge (3) Defer |
| 1+ Test Plan unchecked | (1) Verify unchecked items (web-ui-test/curl) (2) File separate issue then merge (3) Defer |
| 1+ CI failures | (1) Investigate CI cause (2) If failure unrelated to PR, file separate issue (3) Defer |
| Formal Review unapproved | (1) Self-approve (2) Request reviewer (3) Defer |
| AI Review Summary not posted | **Cannot reach this stage** — Step 7 requires posting |

### Deferred Actionable tracking option (MANDATORY — when merging + Critical/Minor not applied)

When pushing a merge while not immediately applying actionable items (Critical, Minor), the **tracking location must be explicitly stated in the option**. Vague descriptions like "subject to separate PR" are forbidden.

**Tracking medium (checklist) branching (per workflow environment)**:

| Environment detection | Tracking medium | Format |
|----------------------|----------------|--------|
| `{workspace}/.ralph/fix_plan.md` exists (Ralph autonomous) | fix_plan.md | `- [ ] [BLOCKED] [REVIEW_FEEDBACK] {reviewer}: {summary} — {action direction}` |
| `{workspace}/checklist.md` exists (Ralph not in use) | checklist.md | `- [ ] [BLOCKED] {summary}` |
| GitHub Issue collaboration workflow | Separate Issue | `gh issue create` — specify "deferred from PR #N" in title/body |
| Handled by additional commit in the same PR | Separate commit | Do not use "subject to separate PR" — push to this PR |

**Option description requirements**:

When a merge option entails deferred actionable items, the description must include all of:
1. AI Review Summary URL (passes block-merge-without-review.sh)
2. **Tracking location of deferred items** (checklist / Issue number)
3. **Form of deferred items** (`[BLOCKED]`, `[REVIEW_FEEDBACK]`, Issue title, etc.)

**Deferred scope branching (MANDATORY — branching options required if 2+ actionable items)**:

If actionable items (Critical + Minor + Refactor) total 2 or more, do not create a single "Critical only" option; instead present **3-way branching options**:

| Branch | Applicable case | description example |
|--------|----------------|---------------------|
| **Critical only deferred** | When Minor is applied immediately or decided to be ignored | "Critical 1 item checklist [BLOCKED] + Minor ignored in this PR (No action)" |
| **Minor only deferred** | When Critical is applied immediately | "Critical applied immediately + Minor in checklist [BLOCKED]" |
| **All deferred** | All actionable items handled in next session or separately | "Critical + Minor all in checklist [BLOCKED]" |

**Option example (GitHub Issue environment, 1 Critical + 2 Minor)**:

```typescript
[
  {
    label: "Merge PR + Critical only as separate Issue",
    description: "AI Review Summary posted (URL) | 1 Critical filed as new Issue + 2 Minor No action. squash merge"
  },
  {
    label: "Merge PR + all actionable as separate Issues",
    description: "AI Review Summary posted (URL) | Critical + Minor all filed as Issues × 3 (title: \"deferred from PR #N: {summary}\"). squash merge"
  }
]
```

**Reinforced self-check** (immediately before option drafting — additional items):

5. If actionable items total 2 or more, are all **3 branching options** included? (Critical only deferred / Minor only deferred / All deferred — matching the branching table above)
6. Is "All deferred" always included as one of the recommended options regardless of the number of actionable items?

**Don't / Do table**:

| # | Don't | Do |
|---|-------|-----|
| 1 | Abstract description like "subject to separate PR" | Specify tracking medium (fix_plan.md/Issue/checklist) + form (`[BLOCKED]`, etc.) |
| 2 | Push medium decision onto the user without autonomous determination | Auto-detect environment (whether `.ralph/fix_plan.md` exists) and present medium options |
| 3 | Omit form of deferred items (`[BLOCKED]`, Issue title) | Indicate form inline in the option description |
| 4 | Omit tracking location after "Critical to be handled later separately" | Bundle immediate registration in the tracking medium as a task right after merge |

**Self-check (immediately before option drafting)**:

1. Does the merge option entail 1+ unapplied actionable items?
2. Has the tracking medium been determined per environment (whether `.ralph/` exists)?
3. Does the option description include all of (a) AI Review Summary URL (b) tracking location (c) form?
4. Is the post-merge tracking-medium registration bundled as a separate executable task?
5. **Reject findings axis check (HARD STOP — 2026-05-24)**: are there 1+ findings auto-classified as Reject in Step 4? → If yes, **Reject findings must appear as a user-override option** in this Step 8 ask. See "Reject finding option mandate" below

### Reject finding option mandate (HARD STOP — added 2026-05-24)

**A Reject decision must also be user-overridable.** Even if Step 4 auto-classified a finding as Reject via the `superpowers:receiving-code-review` "Push back when wrong" procedure, the Step 8 next-action ask must **expose that Reject decision to the user**. If Reject disappears from the options, the user cannot choose "apply it anyway" / "keep it Rejected" → Resume scope shrinks.

#### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | After auto-classifying Reject in Step 4, fully exclude the Reject finding from the Step 8 ask options | Expose the Reject finding to the user as a separate option or axis. The user can decide to override Reject |
| 2 | "The Reject rationale (repo convention, etc.) is clear, so omitting the option is OK" thinking | Even with a clear rationale, the user decision step is separate. Reject = AI judgment, override = user authority |
| 3 | Assume "Accept/Defer options alone are enough" | Present all three to the user: Accept option / Defer option / **Reject override option** |
| 4 | Assume "the Push back when wrong procedure has no user-confirmation step, so auto-Reject is OK" | superpowers is an evaluate→respond framework. The Step 8 ask is the final decision gate. Two separate domains |

#### Option design pattern (when a Reject finding exists)

```typescript
[
  {
    label: "Apply Accept findings + Reject as-is (Recommended)",
    description: "AI Review Summary posted (URL) | Accept N items applied + Reject M items kept (reason: <repo convention etc.>)"
  },
  {
    label: "Apply ALL findings (override Reject)",
    description: "AI Review Summary posted (URL) | Accept N + Reject M (override — user decided to apply despite the pushback reason)"
  },
  {
    label: "Defer all findings",
    description: "AI Review Summary posted (URL) | fix_plan [BLOCKED] [REVIEW_FEEDBACK] for Accept N + Reject M (override option preserved)"
  },
  {
    label: "Hold",
    description: "Decision pending"
  }
]
```

A **Reject-only application option** is also possible (e.g., Accept defer + Reject override):
```typescript
{
  label: "Override Reject only (defer Accept)",
  description: "AI Review Summary posted (URL) | Reject M applied (user override) + Accept N deferred to fix_plan"
}
```

#### Self-check (every time before option drafting)

1. Are there 1+ Reject findings in the Step 4 classification?
2. If yes, did you include a Reject override option in the Step 8 options?
3. Did you state the Reject rationale in the option description? (gives the user info to judge "is that rationale enough? override?")
4. If only "Accept only" / "Defer only" options are presented = violation (Reject override omitted)

#### Violation case (2026-05-24, 1st occurrence)

In the PR #13 consolidate next-action ask, the Track A options were presented only as "apply 3 deferred Minor" / "keep Defer" / "hold". CodeRabbit Finding 1 (release-please.yml SHA pin) Major was auto-classified as Reject on repo-convention grounds and excluded from the options entirely. The user signaled Reject-override intent with "fix them all together". **The Reject finding was not exposed as a separate option, stripping the user's decision authority.**

### Invocation pattern

```text
Skill("next") with args:
  "After PR consolidate — ask for PR #N handling direction
   - 4-condition status: <CI/Review/TestPlan/Mergeable>
   - AI Review Summary URL: <comment-URL>
   - Option candidates: ..."
```

The next skill performs the AskUserQuestion call + result handling. The consolidate skill is only responsible for invoking next.

### Self-check (on Step 8 entry)

1. Was the Step 7.5 status line output?
2. Is there at least 1 PR handling direction candidate? (including defer)
3. If a merge option is among the candidates, does the description include the attestation?
4. For a single PR, did you decide to route to next; for multiple PRs, to wip?

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Terminate after outputting only the Status line | Invoke next/wip per the routing table |
| 2 | Avoid the ask by reporting "awaiting explicit user instruction" | Defer is also an option — proceed with the ask |
| 3 | Omit attestation from the merge option description | Include "AI Review Summary posted (URL)" → passes block-merge-without-review.sh |
| 4 | Compress 4 PRs into next during a multi-PR consolidate | Route to wip (1 question per PR) |

## Workflow termination

Handle user decisions based on the next/wip invocation result. The consolidate skill terminates here.
