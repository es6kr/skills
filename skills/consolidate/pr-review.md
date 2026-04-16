# PR AI Review Consolidation

Review AI bot feedback (CodeRabbit, Copilot, etc.) on a PR and post an AI Review Summary comment.

## When to Use

- After PR creation, when AI reviews are complete
- User says "review check", "CodeRabbit review", "AI review", "review consolidate"
- **Not** for human reviewer feedback — this is AI bot review only

## Workflow

### Step 1: Identify PR

If no PR number given, detect from current branch:

```bash
gh pr list --head "$(git branch --show-current)" --json number,title --jq '.[0]'
```

### Step 2: Check Skip Conditions

Skip entirely if any of these are true:

1. **CI failing**: `gh pr checks <NUMBER> --json state --jq '[.[] | select(.state != "SUCCESS")] | length'` > 0
2. **Reviews not complete**: CodeRabbit summary comment not yet posted (check for "<!-- walkthrough_start -->")
3. **Already summarized**: `gh pr view <NUMBER> --comments` contains "AI Review Summary"

If skipped, report the reason and stop.

### Step 3: Collect AI Reviews

```bash
# PR review comments (inline)
gh api repos/{owner}/{repo}/pulls/{number}/comments

# PR issue comments (summary)
gh pr view <NUMBER> --comments --json comments
```

Identify reviews from:
- `coderabbitai[bot]` — CodeRabbit
- `copilot[bot]` — GitHub Copilot
- Other bots with `[bot]` suffix

### Step 4: Analyze and Classify

For each AI reviewer, classify feedback:

| Category | Action |
|----------|--------|
| **Actionable** (bug, security, logic error) | Fix required |
| **Suggestion** (style, naming, minor improvement) | Evaluate |
| **Informational** (summary, walkthrough) | No action |

Present classified results to user via text summary. **Do NOT auto-fix anything.**

### Step 5: User Decision

Present findings and ask user what to do:

```
AskUserQuestion({
  question: "How to handle these AI review findings?",
  options: [
    { label: "Fix actionable items", description: "Fix N items, then post summary" },
    { label: "Post summary as-is", description: "No fixes needed, post clean summary" },
    { label: "Skip", description: "Don't post anything" }
  ]
})
```

### Step 6: Fix (if approved)

**Only fix if user explicitly approved in Step 5.**

Branch ownership check before fixing:

| Branch creator | Allowed action |
|----------------|---------------|
| Self (gh issue develop) | Code fix + commit + push |
| Others (dependabot, user branch) | Comment-only — no code changes |

After fixing, commit with message referencing the review:
```
fix: address CodeRabbit review on PR #NUMBER
```

### Step 7: Post AI Review Summary

**Always post a summary comment** (unless user chose "Skip" in Step 5).

```bash
gh pr comment NUMBER --body "## AI Review Summary

- **CodeRabbit**: [actionable items fixed / no actionable comments]
- **Copilot**: [issues found / no issues found]

[All AI reviews passed. Ready to merge. / Fixes applied in commit abc1234.]"
```

Only include reviewers that actually posted reviews on this PR.

## Rules

- **Never auto-fix without user approval** — always go through Step 5
- **Never auto-commit/push without user approval** — fixing requires explicit consent
- **Always post summary comment** — even if no actionable items (unless user skips)
- **Check branch ownership** — only modify code on self-created branches
- **One summary per PR** — skip if "AI Review Summary" already exists
