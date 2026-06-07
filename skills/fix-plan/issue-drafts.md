# Issue Drafts

Lifecycle management for draft files staged for GitHub issue/PR creation.

> **Scaffold placeholder** — Content migration from `ralph/fix-plan.md` (sections L265-324) in progress. See plan `~/.agents/docs/generated/plan-fix-plan-migration.md` §4 for migration matrix.

## Planned Content

### 4-stage lifecycle (CRITICAL)

Each stage must have a clear owner — otherwise stale residue accumulates.

| Stage | Action | Owner |
|-------|--------|-------|
| 1. Write | Create `issue-drafts/<slug>.md` | Author (human or agent) |
| 2. Publish | `gh issue create` / `gh pr create` posts to GitHub | Author |
| 3. **Archive** | `issue-drafts/<slug>.md` → `issue-drafts/.bak/<slug>.md` | This topic (auto on next invocation) |
| 4. Delete from fix_plan | Remove the `[x]` entry from `## Issue Drafts` section | This topic |

**Order is mandatory**: archive **first**, fix_plan delete **second**. Reverse order leaves the file in `issue-drafts/` → next sync misclassifies it as "still pending".

### Archive procedure

When this topic is invoked, scan `## Issue Drafts` for items matching all conditions:

1. fix_plan entry is `[x]` or `[DONE]`
2. Body cites the draft filename (e.g., `web-each-key-duplicate.md`)
3. The file actually exists in `issue-drafts/` (not already in `.bak`)
4. Entry references `Issue #N` or `PR #N` (publish-trace evidence)

Archive command:

```bash
mkdir -p issue-drafts/.bak
mv issue-drafts/<slug>.md issue-drafts/.bak/
```

After archive → delete fix_plan entry (next section).

### Delete rule

**Archived entries are removed from `## Issue Drafts` entirely.**

- Do not use a `[DONE]` tag — completion = archive + entry removal
- Rationale: `## Merged / Closed` section already records the Issue/PR number; leaving a residual entry is duplicate noise

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | `[x]`-check the fix_plan entry but leave the file in `issue-drafts/` | Archive (`mv → .bak/`) **first**, then delete the fix_plan entry |
| 2 | Ad-hoc AskUserQuestion "what to do with the `[x]` entry?" | Invoke this topic — archive + delete is automatic |
| 3 | Keep a `[DONE]` tag in fix_plan | Archive, then remove the entry entirely. Merged/Closed section is sufficient tracking |
| 4 | Skip archive → next invocation re-detects as "pending draft" | Archive every time this topic runs |
