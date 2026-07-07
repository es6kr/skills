# Task Completion Report Format

When marking a task `completed`, **always emit a one-line title plus a 1-2 sentence change summary**. Empty "done" reports are forbidden — the user must be able to see what changed without inspecting other artifacts.

## When TodoWrite is mandatory

Use TodoWrite **before the first tool call** in the following cases:

- A task with 2+ steps before starting
- Complex migrations or multi-step workflows
- Whenever 2+ issues/PRs are involved
- Whenever `gh issue edit` / `gh pr edit` is going to be called 2+ times in a row
- When the fix_plan declares a solution sequence (`#A → #B → #C`), register each as a task

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat a quick user instruction as "too small for TodoWrite" | Add it as a pending task immediately, then begin work — preserves the original-task context |
| 2 | Skip TodoWrite because "the requirement is one line" | One-line follow-ups are still follow-ups. Register them so they are traceable |
| 3 | When a local-deploy instruction hits an auth error, fall back to a remote workflow trigger | Resolve the local auth failure (e.g., ask the user to `npm login`) and run the local deploy command as instructed — never silently switch to a CI workflow as a workaround |

### Forbidden

- Using TodoWrite only at the end to list results after the fact
- Reporting "done" after a long run with no TodoWrite trail
- Marking everything completed at once with no intermediate progression
- Running `gh issue edit` / `gh api` 2+ times in a row without TodoWrite — register first, then execute in order

## Completion report format

When calling `TaskUpdate(status: "completed")`, the response text MUST follow:

```text
**{task title}** — {1-2 sentence change summary}
```

- Forbidden: `Done. Other agents pending.` (says nothing about what was done)
- Forbidden: `Committed 199438c.` (does not say whether new commit or amend)

### Open Test Plan items block terminal language

Do not declare a task / PR cycle **"end / done / complete / finished / wrapped up"** while the PR Test Plan still has any unchecked `- [ ]` item — **including `**[post-merge]**` items**. `[post-merge]` does not block merge, but an open post-merge verification means the work is NOT finished; report it as *merge-complete with post-merge verification still tracked*, naming each open item + its trigger.

| # | Don't | Do |
|---|-------|-----|
| 1 | "PR #N cycle ends here" while a `- [ ] **[post-merge]**` item is unchecked | "PR #N merged. N post-merge verification items still tracked (trigger: ...)" — name each open item + its tracking trigger |
| 2 | Equate "merge allowed / doesn't block merge" with "work finished" | Merge-gate status ≠ completion status. An open post-merge item is an open deliverable — report it as outstanding |

### Commit-included reports

When the completion involves a commit, the report MUST also include:

1. **Commit SHA**
2. **Commit method** — new commit **or** amend
3. **Target repo + branch**

The commit method matters because amend requires a force push while a new commit ships with a regular push — the user needs the push strategy at a glance.

Example:
```text
**egov OIDC logout implementation** — Added OidcClientInitiatedLogoutSuccessHandler in SecurityConfig.java. New commit 199438c (deps-sso master). Not pushed.
```

## File-change disclosure (HARD STOP)

For tasks that touched files via `Edit` / `Write`, the completion report MUST show the user the actual change — diff or key lines — in chat. A 1-2 sentence summary alone deprives the user of any chance to review the artifact.

| # | Don't | Do |
|---|-------|-----|
| 1 | Just summarize "added env-switch guard section to iac.md" | Show the new section heading + key Do/Don't row(s) or line count + new command example |
| 2 | Plain text "added plan-% / apply-% targets to Makefile" | Show the actual target lines (`plan-%:` block) in chat |
| 3 | Move the task to completed without ever surfacing the diff or capture | Show `git diff <file>` or before/after in chat, then mark completed |
| 4 | Defer with "the change summary is recorded in fix_plan / improvements.md" | Tracking-medium records are additive; user-facing disclosure goes in chat separately |

### Disclosure format by size

- **1-3 line change**: paste the changed lines directly in chat
- **4-20 line change**: section title + key excerpt (e.g., 1 row from the Do/Don't table)
- **20+ line change**: changed files + section structure (heading list) + key excerpt. Skeleton, not the whole body
- **New file**: file path + first 10-20 line excerpt

## PR comment for AI-assisted work — not needed on code PRs

When the PR is itself a code-change PR, the commit messages and the commits are the work-tracking medium. Any rule / skill edits the AI made alongside should be recorded in `fix_plan` / `improvements.md`; a separate PR comment is noise.

| # | Don't | Do |
|---|-------|-----|
| 1 | Post a separate PR comment summarizing AI-side rule / skill edits that ride along the PR | Record only in `fix_plan` / `improvements.md`. The edits are outside the PR scope; a comment is noise |
| 2 | Add a comment "for whole-flow visibility from the PR perspective" | PR perspective = the PR commits themselves. External-medium work belongs in external-medium tracking |
| 3 | Autonomously comment on the user's own PR | PR comments are for external feedback responses, formal reviews, Test Plan / verification — content directly relevant to the PR itself |

### Exceptions — PR comments are appropriate when

- Responding to external feedback (CodeRabbit, reviewer)
- Posting the AI Review Summary via the consolidate skill
- Registering PR Test Plan / verification results
- Posting context directly tied to the PR (deploy plan link, related-issue cross-reference)

## Reference

See `~/.claude/skills/cleanup/data/failed-attempts.md` "completion report" and "file-change disclosure" entries for recurrence history.
