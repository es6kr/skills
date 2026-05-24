# User Decision + Fix

Present classification results to the user from Step 4 and decide on two axes (Findings handling + Formal Review action). fix when approved + Pushback procedure (Rejected).

Entry: `Skill("consolidate", "decide ...")` or `pr.md` Workflow Step 5 / Step 6.

## Step 5: User Decision

Present findings and ask user what to do. **Branch on two axes**: (a) findings handling, (b) Formal Review action (when you are a requested reviewer).

### Axis A: Findings handling

**Option description must reflect the medium decided in Step 7 medium selection** (Mergeable + Formal Review action → unified POST). When unified POST applies, "post summary" means "post Summary body as Formal Review body" (single POST). Otherwise it means "post Summary as issue comment".

```javascript
// Mergeable + Formal Review action (unified POST will apply)
AskUserQuestion({
  question: "How to handle these AI review findings?",
  options: [
    { label: "Fix actionable items", description: "Fix N items, then post Summary as Formal Review body (single POST)" },
    { label: "Post summary as-is", description: "No fixes needed. Summary body → Formal Review POST (no separate issue comment)" },
    { label: "Skip", description: "Don't post anything" }
  ]
})

// Non-Mergeable or Skip formal review (separate POST)
AskUserQuestion({
  question: "How to handle these AI review findings?",
  options: [
    { label: "Fix actionable items", description: "Fix N items, then post summary as issue comment" },
    { label: "Post summary as-is", description: "No fixes needed, post Summary as issue comment" },
    { label: "Skip", description: "Don't post anything" }
  ]
})
```

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
