# Collect AI Reviews

Collect AI reviews (CodeRabbit, Copilot, etc.) posted on the PR and load the verify→evaluate→respond framework.

Entry: `Skill("consolidate", "collect ...")` or `pr.md` Workflow Step 3.

## Step 3: Collect AI Reviews

Rather than running separate manual commands, run the consolidated collection script:

```bash
bash ~/.claude/skills/consolidate/scripts/collect.sh <repo> <pr_number> [account]
# e.g., bash ~/.claude/skills/consolidate/scripts/collect.sh daegunsoftDev/turborepo-web 412 daegunjhy
```

If you prefer running individual commands manually:

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

> **Bot login differs by API surface (poll/filter gotcha)**: GraphQL (`gh pr view --json reviews`) returns `author.login` WITHOUT the suffix (e.g. `copilot-pull-request-reviewer`), while REST (`gh api .../pulls/{N}/reviews`) returns `user.login` WITH it (e.g. `copilot-pull-request-reviewer[bot]`). An exact-match jq filter written for one surface silently matches nothing on the other — a completion poll can time out while the review has already arrived. Use a substring/`test()` match (e.g. `test("copilot")`) or match per surface.
- **Human MEMBER/OWNER reviews and review-shaped comments (HARD STOP)** — enumerate every `reviews[]` entry whose `author.is_bot == false`, plus every `comments[]` entry whose `authorAssociation` is `MEMBER`/`OWNER`/`COLLABORATOR` AND whose body contains a review-style header (Code Review headers, `### Findings`, `### Issues`, `Critical`, `Important`, `Should fix`, `Must fix`, localized equivalents in any language). Each such reviewer (login) is a distinct **Source** that must be carried forward into the findings table — do not collapse them under "Internal Code Review". Query: `gh pr view <N> --json reviews,comments --jq '[.reviews[] | select(.author.is_bot==false) | {kind:"review", login:.author.login, body}] + [.comments[] | select(.authorAssociation == "MEMBER" or .authorAssociation == "OWNER" or .authorAssociation == "COLLABORATOR") | {kind:"comment", login:.author.login, body}]'`. Cross-check returned bodies for review-style headers before declaring a `comment` entry a review source.

### Zero-findings completion state (do NOT treat as missing review)

CodeRabbit's summary comment "**No actionable comments were generated in the recent review**" is a **completed review with verdict 0 findings** — the walkthrough is usually collapsed inside that same comment. It is NOT a rate-limit / pending / failure state, and it is NOT grounds for a re-review trigger (see `pr.md` Step 2.6 state matrix).

Handling: record the reviewer in the matrix with verdict "no actionable findings" and continue to classify/post — `post.md` already supports a clean-reviewer row ("state 'No actionable findings' in the table if all reviewers are clean").

### Source-Specific Handling

All AI reviewers are **external reviewers** — treat their suggestions as proposals to evaluate, not orders to follow.

| Reviewer | Strengths | Watch out |
|----------|-----------|-----------|
| **CodeRabbit** | Full codebase context, walkthrough, security checks | Can suggest over-engineering; may not understand project conventions |
| **Copilot** | Inline code suggestions, style consistency | May miss cross-file context; suggestions can break other callers |

Before accepting any suggestion:
1. Check: Technically correct for THIS codebase?
2. Check: Breaks existing functionality or callers?
3. Check: Reason for current implementation? (grep for usage)
4. Check: Works on all platforms/environments?
5. Check: Conflicts with user's prior architectural decisions?

## Step 3.6: Invoke superpowers:receiving-code-review

**MANDATORY**: Before analyzing, invoke the review-receiving skill to load the verification framework:

```text
Skill("superpowers:receiving-code-review")
```

This loads the verify→evaluate→respond protocol. Follow it for every feedback item in Step 4 (classify).

**Proactive Plugin Installation (HARD STOP)**: `superpowers` MUST be installed as a **plugin** (`obra/superpowers`), NOT as individual skills via `npx skills add`. If the plugin is not present, install it via the plugin management mechanism:
```bash
# Plugin installation for superpowers
claude plugin add obra/superpowers
```
Check and install any other missing peer skills or plugins (like `git-repo` or `github-flow` from `es6kr/skills`) in the same manner.

**Abort if unavailable (HARD STOP)**: If the skill remains unavailable even after the installation attempt, or if the installation command fails, **immediately abort the consolidate procedure**. Report to the user "Cannot use the `superpowers:receiving-code-review` skill; aborting consolidate" and terminate. Analyzing reviews without the verify→evaluate→respond framework risks blind acceptance, so alternative continuation is prohibited.

## Re-checking a previously-posted AI Review Summary

When following up on a `[REVIEW_FEEDBACK]` fix_plan entry (checking whether a previously-deferred finding is still outstanding), don't re-parse `gh pr view --json comments`'s output by hand — extract the already-posted Findings table structurally:

```bash
uv run python ~/.claude/skills/consolidate/scripts/extract-review-findings.py <owner/repo> <pr_number>
```

Prints `{"comment_url": "...", "findings": [{"#": "1", "Source": "...", ...}, ...]}` — one dict per row, keyed by whatever column headers the table actually used (column layout varies slightly across sessions — e.g. `Source`/`Location` vs `Reviewer`/`File:Line`). Errors with `{"error": "no AI Review Summary comment found"}` (exit 1) if the PR has no posted summary yet.

## Next

→ If the external AI review is walkthrough only / in a failure state, go to `internal.md` (Step 3.5 Internal Review Fallback)
→ Otherwise, go to `classify.md` (Step 4 Analyze and Classify)
