# PR AI Review Consolidation

Review AI bot feedback (CodeRabbit, Copilot, etc.) on a PR and post an AI Review Summary comment.

## When to Use

- After PR creation, when AI reviews are complete
- User says "review check", "CodeRabbit review", "AI review", "review consolidate"
- **Not** for human reviewer feedback — this is AI bot review only

## Role Terminology Definitions (HARD STOP — avoid confusion in conversation/comments)

| Term | Meaning | Example |
|------|---------|---------|
| **author** | The person who created the PR. The party who pushes commits and applies feedback | `<pr-author>` (PR #N) |
| **reviewer** (GitHub) | The person requested to review the PR. Has Formal Review (APPROVE/REQUEST_CHANGES) authority | `<github-reviewer>` |
| **code-reviewer** (subagent) | AI subagent dispatched as Internal Review Fallback | `Agent(subagent_type: "code-reviewer")` |
| **AI reviewer** (bot) | External AI review bots such as CodeRabbit, Copilot | `coderabbitai[bot]` |

| # | Don't | Do (correct alternative) |
|---|-------|--------------------------|
| 1 | Calling the PR author a "reviewer" | "author (`<pr-author>`) applied the commit" — specify role explicitly |
| 2 | "The reviewer pushed a commit" (attributing author's action to reviewer) | "author added a commit applying the review feedback" |
| 3 | Automatically mapping "reviewer" to author when user says it | In consolidate context, "reviewer" defaults to code-reviewer subagent. If ambiguous, AskUserQuestion |

## Workflow Index

| Step | Topic file | Responsibility |
|------|-----------|----------------|
| 1 (Identify PR) + 2 (Skip Conditions) + 2.5 (Copilot sequential) + 2.7 (worktree checkout) | (inline in this file) | PR identification + skip judgment + Copilot sequential execution + check out PR branch into a worktree |
| 3 (Collect AI Reviews) + 3.6 (superpowers:receiving-code-review) | [`collect.md`](./collect.md) | AI review collection + load verify→evaluate→respond framework |
| 3.5 (Internal Review Fallback) + 4.5 (UI capture verification) | [`internal.md`](./internal.md) | Post Internal Code Review comment on walkthrough only/Copilot failure + verify captures on UI-change PRs |
| 4 (Analyze and Classify) | [`classify.md`](./classify.md) | dual-label (Type \| Severity) classification + PR diff scope cross-check + option grouping |
| 5 (Formal Review Decision — Axis B only) + 6 (Fix or Reject — only on explicit instruction) | [`decide.md`](./decide.md) | Axis B (Formal Review) ask when requested reviewer. **Axis A (Findings handling) ask is forbidden (HARD STOP)** — posting the Summary is procedure |
| 7 (Auto-Post AI Review Summary + Formal Review) + 7.5 (Status line) + 7.6 (Auto-register Deferred Findings) | [`post.md`](./post.md) | Auto-post the Summary (no user decision) + auto-register Findings to fix_plan `[REVIEW_FEEDBACK]` (defer by default) |
| 8 (Post-Summary Next-Action Ask) | [`next.md`](./next.md) | Merge/fix-deferred/hold option ask (fix only on explicit user instruction at this step) |

Entry order: Step 1 → 2 → (2.5 multi-PR only) → 2.7 (worktree checkout) → [collect](./collect.md) → [internal](./internal.md) (conditional fallback) → [classify](./classify.md) → [decide](./decide.md) → [post](./post.md) → [next](./next.md).

## Step 1: Identify PR

If no PR number given, detect from current branch:

```bash
gh pr list --head "$(git branch --show-current)" --json number,title --jq '.[0]'
```

## Step 2: Check Skip Conditions

Skip entirely if any of these are true:

1. **CI failing**: `gh pr checks <NUMBER> --json state --jq '[.[] | select(.state != "SUCCESS")] | length'` > 0
2. **Reviews not complete**: CodeRabbit summary comment not yet posted (check for "<!-- walkthrough_start -->")
3. **Already summarized**: `gh pr view <NUMBER> --comments` contains "AI Review Summary"

> **Bash exit code caveat**: `grep -c` returns exit code 1 when there are zero matches. When chaining multiple commands with `grep` last, add a `|| true` guard to prevent false-positive errors.

If skipped, report the reason and stop.

## Step 2.5: Sequential Copilot Review Execution (when consolidating multiple PRs)

When consolidating multiple PRs and Copilot review requests are needed:

1. **Search the checklist for `[COPILOT_PENDING]`** — verify whether a previously requested review is still in progress
2. **If PENDING exists, check that PR**: use `gh pr view <N> --comments` to confirm whether the Copilot review is complete
   - Complete → update checklist `[COPILOT_PENDING]` → `[COPILOT_DONE]`
   - Incomplete → wait (do not submit new requests on other PRs)
3. **When no PENDING exists or after confirming completion**: also check the Copilot review status of the remaining open PRs (`gh pr list --state open`) and batch-update the checklist
4. **Request a Copilot review on only one next PR** → record `[COPILOT_PENDING] PR #N` in the checklist

> **History of repeated failures**: 2026-04-27 batch invocation of 7 reviews all failed; 2026-04-28 parallel review depleted quota

## Step 2.7: Checkout PR branch into a worktree (MANDATORY — all reviews)

After skip conditions pass, check out the PR's head branch into a local worktree **before** collecting reviews. Every review runs against real local files, not just `gh pr diff`. Benefits: the code-reviewer (Step 3.5) reads actual files + can run tests/build, `mergeable: CONFLICTING` is confirmed locally, and inline review line numbers (Step 7) match HEAD exactly.

### Procedure

1. **Resolve PR head branch + base + cross-repo flag**:
   ```bash
   gh pr view <N> -R <owner>/<repo> \
     --json headRefName,headRefOid,baseRefName,mergeable,isCrossRepository,headRepositoryOwner \
     --jq '{branch: .headRefName, head: .headRefOid, base: .baseRefName, mergeable, fork: .isCrossRepository, headOwner: .headRepositoryOwner.login}'
   ```
   - `base` (`baseRefName`) is the merge target — needed for the CONFLICTING detection step below.
   - `fork` (`isCrossRepository`) flips the fetch strategy in step 2.
2. **Fetch head + base**:
   - **Same-repo PR** (`fork == false`): `git -C <repo> fetch origin <headRefName> <baseRefName>` — both refs live on `origin`.
   - **Fork PR** (`fork == true`): `origin` does not carry the fork's head. Use `gh pr checkout <N> -R <owner>/<repo> --recurse-submodules=no --force` *inside the worktree from step 3*, which creates a local tracking branch from the fork via the API. Then `git -C <worktree> fetch origin <baseRefName>` for the base.
3. **Acquire a worktree via the `git-repo` `worktree` topic** — do NOT `git worktree add` blindly. Follow git-repo's decision tree: reuse an inactive / merged-PR worktree first (rename to this PR's branch), else create at `.claude/worktrees/<branch>`. (`git-repo` is a `depends-on` of this skill.)
4. **Record the worktree path.** All subsequent steps operate there: the code-reviewer dispatch (Step 3.5) gets the worktree path, local verification runs in it, and Step 7 inline line lookups read files from it.

### CONFLICTING detection (report, do not resolve)

If `mergeable` is `CONFLICTING`, the worktree lets you confirm the conflicting files locally (uses `baseRefName` resolved in step 1):

```bash
git -C <worktree> merge --no-commit --no-ff origin/<baseRefName> 2>&1 | grep -i conflict
git -C <worktree> merge --abort   # always abort — do not commit a merge into the PR branch
```

Report the conflicting files in the Summary so the author can rebase. **Do not resolve another author's conflict** (branch ownership: only the PR author resolves — see [`~/.agents/rules/git.md`](~/.agents/rules/git.md) "Branch ownership" rule).

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Review only from `gh pr diff` with no local checkout | Check out the PR branch into a worktree first; the code-reviewer reads real files + runs tests |
| 2 | `git worktree add` a fresh worktree every review | Use the git-repo `worktree` topic — reuse inactive / merged-PR worktrees first (decision tree) |
| 3 | Resolve a CONFLICTING PR's conflict in the worktree | Detect + report conflicting files. Branch ownership: only the author resolves |
| 4 | `git worktree remove` after every review | Leave it for git-repo to reuse next review. Do not delete blindly |
| 5 | Skip the worktree when external AI review is already sufficient | Worktree is mandatory for **all** reviews — it enables CONFLICTING detection + local verification regardless of external AI completeness |

### Self-check (before Step 3 collect)

1. Did you resolve `headRefName` and fetch it?
2. Did you acquire the worktree via git-repo's worktree topic (reuse-first), not a blind `git worktree add`?
3. Is the worktree path recorded for the code-reviewer dispatch + inline lookups?
4. If CONFLICTING, did you confirm the conflicting files locally and abort the test-merge?

## Rules

- **PATCH the same comment when updating; never add a parallel comment + overwrite the old one (HARD STOP)**: If a previous session's Internal Review/AI Review Summary comment already exists on the same PR, update **that same comment** in place via `gh api PATCH` with the new same-kind content (Internal Review → Internal Review update; Summary → Summary update). PATCHing the same comment with same-kind content is the intended use — the prior content is replaced, but no other comment is touched. **What is forbidden**: adding a new comment AND then PATCHing the previous comment's body with placeholder/minimize text (e.g., `_(minimized)_`) to "hide" the old one — that permanently destroys the original content of the previous comment.

  | # | Don't | Do (correct alternative) |
  |---|-------|--------------------------|
  | 1 | Adding a new `gh pr comment` when a same-kind comment already exists | Update the existing comment with `gh api repos/{owner}/{repo}/issues/comments/{id} -X PATCH -f body=...` (same-kind content) |
  | 2 | Adding a new comment then PATCHing the previous comment body with placeholder/minimize text | Do not touch the previous comment. If a new comment is needed, keep the previous one intact |
  | 3 | Overwriting the previous comment body with `_(minimized)_` to "hide" it | Preserve the original previous comment. If folding is needed, use GraphQL `minimizeComment(classifier: OUTDATED)` (which does not modify the body) |

- **Never auto-fix without explicit user instruction** — fix (code changes) must not run automatically in Step 5/6. Proceed only when the user explicitly chooses "fix" in the Step 8 next-action ask. Posting the Summary (Step 7) is procedure, so it proceeds automatically without a user decision
- **Never auto-commit/push without user approval** — even after a fix is decided, commit/push needs separate explicit consent
- **Always post summary comment automatically** — regardless of whether actionable items exist. Findings are auto-registered to fix_plan in Step 7.6. Asking whether to post the Summary is forbidden (HARD STOP). For the medium, see the "Medium selection" table in [`post.md`](./post.md)
- **Check branch ownership** — only modify code on self-created branches
- **Formal Review is mandatory when you are a requested reviewer** — issue comment Summary alone does not satisfy the review request
- **One summary per PR** — skip if "AI Review Summary" already exists. On re-run, update via PATCH on the existing comment
- **Verify before accepting** (`superpowers:receiving-code-review`) — grep actual usage, check callers, confirm the suggestion doesn't break existing behavior
- **No blind acceptance** — each Actionable item needs a verification note explaining why it's valid
- **Push back when wrong** — technically incorrect or YAGNI suggestions get Rejected with reasoning, not silently accepted
- **Copilot review requests must be one PR at a time** — parallel requests only deplete quota and may all fail
  - **Status tracking**: when requesting a Copilot review, record `[COPILOT_PENDING] PR #N` in the checklist
  - **Pre-request check**: if the checklist contains `[COPILOT_PENDING]`, first verify whether that PR's review is complete
  - **After confirming completion**: update `[COPILOT_PENDING]` → `[COPILOT_DONE]`, audit all remaining open PRs and batch-update Copilot status in the checklist, then request a review on the next PR
