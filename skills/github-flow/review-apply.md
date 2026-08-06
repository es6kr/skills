# Review Apply

Collect `[REVIEW_FEEDBACK]` deferred items from fix_plan, apply them to the code, and update the PR body/Summary.

This is the **dedicated follow-up entry point** for items that were not applied immediately during consolidate Step 6.

## When to Use

- On requests like "apply review feedback", "review apply", "address feedback", "apply deferred items"
- When `[REVIEW_FEEDBACK]` items in fix_plan still require code changes
- When applying Actionable items that were classified as deferred after consolidate
- On a `[REVIEW_FEEDBACK] processing` instruction

## Workflow

### Step 1: Collect deferred items

Collect every unchecked (`[ ]`) item tagged `[REVIEW_FEEDBACK]` from `fix_plan.md` or `checklist.md` (whichever is present in the workspace — collect from both if both exist):

```bash
Grep("[REVIEW_FEEDBACK]", path="{workspace}/.ralph/fix_plan.md")
Grep("[REVIEW_FEEDBACK]", path="{workspace}/checklist.md")
```

**Information to collect** (per item):

| Field | Example |
|-------|---------|
| PR number | `PR #317` |
| Severity | `🔴 Critical`, `🟡 Minor` |
| File:line | `route.ts:25` |
| Summary | `findMany has no take, risks bulk reads` |
| Original reviewer | `code-reviewer`, `CodeRabbit`, `Copilot` |
| Owner | `teammate in progress`, unassigned, etc. |

### Step 2: Filter the apply targets

| Condition | Action |
|-----------|--------|
| `[ ]` + PR assigned to / authored by me | Apply |
| `[ ]` + marked **teammate in progress** | Skip — do not modify a teammate's PR |
| `[x]` already completed | Skip |
| `[BLOCKED]` tag | Skip — external dependency |

If zero items remain, report and stop.

### Step 3: AskUserQuestion for apply scope

Show the apply targets to the user and confirm scope.

```javascript
AskUserQuestion({
  questions: [{
    question: "Apply scope for N [REVIEW_FEEDBACK] items?",
    header: "Review apply",
    multiSelect: true,
    options: [
      { label: "Apply Critical only", description: "🔴 Critical N items" },
      { label: "Apply Critical + Minor", description: "🔴 N items + 🟡 M items" },
      { label: "Pick individually", description: "Decide apply/skip per item" }
    ]
  }]
})
```

### Step 3.5: Verify current state before applying (HARD STOP — merged-PR / stale-tracker case)

**Before editing any code, check the target PR's merge state and the finding's target file/line against current reality.** A `[REVIEW_FEEDBACK]` item can go stale between when it was recorded and when review-apply runs — the target PR may have already merged, and the finding itself may have already been resolved by unrelated work (or its target file may no longer exist).

```bash
gh pr view <N> -R <repo> --json state,mergedAt
```

**Branch on the result, per item:**

| PR state | Finding's current-code check | Action |
|----------|------------------------------|--------|
| OPEN | (n/a — Step 4 flow applies as written) | Proceed to Step 4 normally |
| MERGED | Target file/line still shows the described defect | Genuinely still broken — proceed, but **Step 6 has no open branch to push to** (see below) |
| MERGED | Target file/line already matches the fix, or the target file no longer exists | **Already resolved / moot** — do NOT re-apply. Correct the tracker instead (see below) |

**Already-resolved / moot handling**: mark the item `[x]` in `fix_plan.md`/`checklist.md` with a one-line note that the code already matched the fix at verification time (not a re-application), and skip Step 4-6 for that item — there is nothing to edit, commit, or push.

**Genuinely-still-broken on a MERGED PR**: Step 4's code edit still applies, but Step 6 cannot push to the original PR's branch (it no longer accepts pushes post-merge). Open a **new** branch + PR for the fix instead, following the repo's normal branching convention (e.g. `fix/<slug>-...` based on the appropriate staging branch) — do not attempt to reopen or force-push the merged PR's branch.

| # | Don't | Do |
|---|-------|-----|
| 1 | Apply a `[REVIEW_FEEDBACK]` item's code change without checking whether the underlying PR already merged | Run the `gh pr view --json state,mergedAt` check first, every item |
| 2 | Treat "finding recorded as unresolved" as proof it's still unresolved | Read the target file/line before editing — the tracker can lag behind actual code state |
| 3 | Try to push a fix commit to a MERGED PR's branch | Open a new branch/PR for genuinely-still-broken findings on a merged PR |
| 4 | Silently drop an already-resolved finding with no tracker update | Mark `[x]` + one-line "already resolved at verification" note — the correction itself is the deliverable for that item |

### Step 4: Apply to code

Process the approved items sequentially (skip items resolved as already-fixed/moot in Step 3.5):

1. **Edit code**: change the code to address the review point
2. **Verify**: confirm the build/tests pass after the change (`pnpm typecheck`, `pnpm test`, etc.)
3. **Commit**: review-application commit
   ```text
   fix: address [REVIEW_FEEDBACK] — {summary}
   ```
4. **Update fix_plan**: check `[ ]` → `[x]` for completed items

### Step 5: Update the PR body / Summary

Update the AI Review Summary status line on the PR that was just addressed:

```bash
# Update the status line on the existing Summary comment
# Status: 4/10 actionable addressed → 7/10 actionable addressed
```

**Update targets**:
- The `status-line` on the AI Review Summary comment (refresh addressed count)
- The PR body Test Plan (check `[x]` for related items)

### Step 6: Push + CI confirmation

```bash
git push origin <branch>
gh pr checks <N>  # wait for CI to pass
```

**MERGED-PR case**: if Step 3.5 opened a new branch/PR (original PR already merged), push to that new branch and watch the new PR's CI — not the original PR number. If Step 3.5 resolved every approved item as already-fixed/moot, there is no commit to push; skip this step entirely.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Check `[REVIEW_FEEDBACK]` items as `[x]` without applying the code change | Edit code → build/tests pass → then `[x]` |
| 2 | Apply `[REVIEW_FEEDBACK]` items belonging to a teammate's PR yourself | Skip teammate-PR items. Relay via a PR comment if necessary |
| 3 | Apply everything without asking the user for scope | Use the Step 3 AskUserQuestion to confirm scope |
| 4 | Apply code without updating Summary / fix_plan | Three-piece set: code apply + fix_plan `[x]` + Summary status-line update |

## Relationship with consolidate

```text
consolidate pr
  Step 4: classify (Actionable / Non-blocking)
  Step 6: immediate apply (with user approval)
  Step 7: post Summary + register deferred items into fix_plan
           ↓
github-flow review-apply  ← follow-up entry point
  Step 1: collect [REVIEW_FEEDBACK] from fix_plan
  Step 4: apply to code
  Step 5: refresh Summary status line
```

consolidate owns **classification + registration**; review-apply owns **follow-up apply + refresh**.
