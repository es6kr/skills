# User Decision (Formal Review) + Fix

Present classification results to the user from Step 4 and decide on Axis B (Formal Review action) only. AI Review Summary posting and Findings deferred registration are **procedure** (Step 7 / 7.6), not user decisions. fix is only executed when the user explicitly instructs (typically via Step 8 next-action or follow-up turn).

Entry: `Skill("consolidate", "decide ...")` or `pr.md` Workflow Step 5 / Step 6.

## Step 5: Formal Review Decision (Axis B only)

**Axis A (Findings handling) ask is forbidden (HARD STOP — 3 recurrences 2026-05-24)**.

The AI review handling flow is procedure:
- Condition (a): CodeRabbit walkthrough + Copilot review both posted normally → Step 7 auto-post AI Review Summary
- Condition (b): CodeRabbit walkthrough only OR Copilot error → Step 3.5 Internal Review Fallback → Step 7 auto-post AI Review Summary
- Actionable findings → Step 7.6 auto-register to fix_plan.md `[REVIEW_FEEDBACK]` (defer by default)
- fix is a **separate step only on explicit user instruction** (Step 8 next-action or a follow-up turn like "apply the review")

**Step 5 is Axis B (Formal Review action) only**. Ask only when you are a requested reviewer. Otherwise skip Step 5 and proceed directly to Step 7.

### Axis B ask precedes Summary medium decision/posting (HARD STOP — added 2026-05-26)

**When you are a requested reviewer, the Step 5 Axis B ask MUST precede the Step 7 Summary posting (whether issue comment or Formal Review body).** "Summary = procedure (automatic)" applies only to **Axis A (findings handling / whether to post)**, **not to the medium decision**. The Summary's medium (issue comment vs Formal Review body) is **dependent on the Axis B answer**, so posting the Summary in any medium before the Axis B answer strips the user of their Formal Review decision authority.

#### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | As a requested reviewer, post the Summary as an issue comment without the Axis B ask | Axis B ask **first** → decide the medium per the answer (APPROVE/COMMENT/REQUEST_CHANGES/Skip) → then post |
| 2 | Execute post.md's "Non-Mergeable → issue comment only, Formal Review skipped" auto-rule without asking when `mergeable: CONFLICTING` | Even when CONFLICTING, a requested reviewer asks Axis B first. The medium auto-skip applies **only after** the ask answer |
| 3 | "Summary is automatic procedure, so post it now and handle Axis B later" | "Summary auto-post" is limited to Axis A (whether to post). The medium depends on Axis B → ask first |
| 4 | Evaluate post.md's medium table before the Axis B ask to fix the medium | The medium table takes **both** the Axis B answer + mergeable. Do not finalize the medium while Axis B is unanswered |

#### Self-check (every time before posting the Summary — HARD STOP)

1. Are you a requested reviewer? (`gh pr view --json reviewRequests` + cross-check active account) → If No, this gate does not apply (auto-post issue comment OK)
2. If Yes, **has the Axis B ask already been answered?** → If No, **posting the Summary is forbidden**. Call the Axis B ask first
3. Only after the Axis B answer, decide the medium (feed the Axis B answer + mergeable into the post.md Step 7 medium table)
4. If the thought "it's CONFLICTING so it's an issue comment anyway" arises = violation signal. Even CONFLICTING requires the Axis B ask first

#### Violation case (2026-05-26, 1st occurrence)

In a consolidate run on a PR where the operator was a requested reviewer, after confirming `mergeable: CONFLICTING`, post.md's "Non-Mergeable → issue comment only" rule was executed without the Axis B ask → the AI Review Summary was auto-posted as an issue comment. The user pointed it out (the Summary was posted in a non-Formal-Review medium without asking). The Axis B ask should have preceded the medium decision. Resolved with a manual APPROVE + this gate added.

### Don't / Do — Axis A ask forbidden (HARD STOP)

| # | Don't | Do |
|---|-------|-----|
| 1 | Call an Axis A ask ("Post summary as-is / Fix actionable items / Skip") | Proceed automatically to Step 7. Posting the Summary is procedure, not a user decision |
| 2 | Ask the user about Findings handling | Findings are auto-registered to fix_plan.md `[REVIEW_FEEDBACK]` in Step 7.6 (defer by default) |
| 3 | "fix is more natural, so Recommended" / "it's Critical/Important, so recommend fix" thinking | fix only on explicit user instruction. No auto-recommendation |
| 4 | Apply the archive rule "no auto-application" to Summary posting too | "No auto-application" applies only to fix (code changes). Summary posting is procedure (separate domain) |
| 5 | Bundle Summary posting + Findings handling into one ask | Summary = procedure (automatic), Findings = auto deferred registration. fix is a separate step (Step 8 or explicit instruction) |

### Self-check (before entering Step 5)

1. Are you a requested reviewer? (`gh pr view --json reviewRequests`) → If Yes, ask Axis B only. If No, skip Step 5 → Step 7
2. Are you building an Axis A option? → Don't. Proceed automatically to Step 7
3. If a "Fix actionable items" or "Whether to post the Summary" option appears = violation

### Axis B: Formal Review action (HARD STOP — required when you are a requested reviewer)

**Pre-check: am I a requested reviewer?**

```bash
GH_TOKEN="$(gh auth token --user <account>)" \
  gh pr view <N> -R <owner>/<repo> --json reviewRequests --jq '.reviewRequests[].login'
# Match against current `gh auth status` active account
```

If the current account appears in `reviewRequests`, present a second ask (in addition to Axis A):

```javascript
AskUserQuestion({
  question: "Formal Review action (you are a requested reviewer)?",
  options: [
    { label: "APPROVE", description: "Findings clean / Critical 0 / merge OK" },
    { label: "REQUEST_CHANGES", description: "Critical findings exist — block merge" },
    { label: "COMMENT only", description: "No formal verdict — just post review body" },
    { label: "Skip formal review", description: "Issue comment Summary only (no PR-level review)" }
  ]
})
```

**Why both axes are required**: Findings handling (A) decides whether to fix code + post an issue comment. Formal Review (B) is a separate medium — GitHub PR review state (APPROVE / CHANGES_REQUESTED / COMMENTED) that gates merge. A "post summary as-is" (A) without an APPROVE (B) leaves the PR blocked by an unfulfilled review request even if all CI/tests pass.

#### Conditional gate: merge-recommendation verdict → no Skip option (HARD STOP)

**If the AI Review Summary verdict in Step 7-A indicates merge recommendation** (🟢 / "Merge OK" / "Ready to merge" / "Merge ready"), remove the `Skip formal review` option from Axis B. The user must choose APPROVE / REQUEST_CHANGES / COMMENT — not Skip. Reason: Skip leaves `reviewDecision: REVIEW_REQUIRED` unresolved, contradicting the merge-recommendation verdict.

```javascript
// When AI Review Summary verdict = merge-recommendation
AskUserQuestion({
  question: "Formal Review action (Summary verdict = merge recommendation — Skip not allowed)?",
  options: [
    { label: "APPROVE", description: "Findings clean / Critical 0 / merge OK — default for merge-recommendation verdict" },
    { label: "REQUEST_CHANGES", description: "Re-evaluation: Critical findings actually exist — block merge" },
    { label: "COMMENT only", description: "Verdict reconsidered: post review body without merge gating verdict" }
  ]
})
```

If the Summary verdict is non-merge (Critical findings exist, Test Plan incomplete, CI failing), keep all 4 options including Skip.

| # | Don't | Do |
|---|-------|-----|
| 1 | Decide only Axis A and post issue comment, then end | Decide both Axis A and Axis B before entering Step 6/7. Axis B is mandatory when you are a requested reviewer |
| 2 | Assume "Summary comment counts as APPROVE" | Issue comment ≠ Formal Review. GitHub merge gates check the `reviews` array, not issue comments |
| 3 | Skip Axis B because findings are clean | Clean findings + requested reviewer = APPROVE (default), still requires the explicit POST |
| 4 | Present Skip option when Summary verdict is merge-recommendation | Remove Skip option for merge-recommendation verdicts. Skip + merge-OK verdict = contradiction (reviewDecision unresolved) |
| 5 | Post Summary verdict = "🟢 merge OK" but answer Axis B as Skip | Summary verdict and Formal Review action must align — merge-recommendation Summary mandates APPROVE/REQUEST_CHANGES/COMMENT |

### Step 5 AskUserQuestion option drift forbidden

Step 5 asks only "whether to post Summary" + "whether to proceed with fixes". **Detailed fix-scope options like "which Critical to apply" belong in Step 6**. If the Step 5 question drifts into a "fix-scope multiSelect", it's a signal that both Step 3.5.3 and Step 7 (posting) are being forgotten.

## Step 6: Fix or Reject (if approved)

**Only fix if user explicitly approved in the Step 5 Axis A ask.** No exceptions even for Critical. **Critical items must be fully fixed and verified before Step 7 Summary posting** (see the "Fixing accepted items" subsection below) — this is consistent with Step 5 approval because the Axis A ask is the gate for any fix work; Step 8 is the post-Summary merge ask, not a separate fix gate.

| # | Don't | Do |
|---|-------|-----|
| 1 | code-reviewer reports "Must Fix" → immediately execute Edit | Wait for Step 5 Axis A approval → Edit → Critical fully verified → Step 7 Summary post → Step 8 merge ask |
| 2 | Skip ask with "Critical, so of course fix it" reasoning | Even Critical requires Step 5 user approval before fixing. Severity ≠ autonomous fix authority |
| 3 | Receive code-reviewer result → skip posting review comment → fix immediately | Post Step 3.5.3 comment → Step 4 classification → Step 5 Axis A approval → Step 6 fix → Step 7 Summary → Step 8 merge ask |

### Branch ownership check before fixing

| Branch creator | Allowed action |
|----------------|---------------|
| Self (gh issue develop) | Code fix + commit + push |
| Others (dependabot, user branch) | Comment-only — no code changes |

### Pushback procedure (for Rejected items)

When a suggestion is technically incorrect, YAGNI, or conflicts with architecture:

1. Write a concise technical reason (not defensive, not performative)
2. Reply in the PR review thread: `gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies -f body="..."`
3. Record in checklist as `[REJECTED]` with reason

Example pushback:
```text
Suggestion: "Add retry logic for this API call"
Rejection: "Caller already handles retries (see middleware.ts:45). Adding here creates double-retry. YAGNI."
```

### Fixing accepted items

**Critical items must be fixed AND verified before proceeding to the next stage (Summary posting, merge recommendation):**

1. Code fix + commit + push
2. Wait for CI pass (`gh run watch` or `gh pr checks`)
3. Check `[x]` for the corresponding item in PR Test plan (`gh pr edit --body`)
4. Post Summary and recommend merge only after verification is complete

The "Shall we merge?" question is allowed only after all Critical items have been fully verified.

After fixing, commit with message referencing the review:
```text
fix: address CodeRabbit review on PR #NUMBER
```

### 'Apply' interpretation rule for user instructions

When the user specifies an application scope such as "apply only X" or "don't apply X", it **by default means code implementation scope**. If AI Review Summary editing is required, the user explicitly states the target like "in the Summary" or "remove from the review". When the target is unclear, **use AskUserQuestion to confirm "is it code implementation scope or Summary editing?"** — arbitrary interpretation is forbidden.

## Next

→ `post.md` (Step 7 Post AI Review Summary + Formal Review)
