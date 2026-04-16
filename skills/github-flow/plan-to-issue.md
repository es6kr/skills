# Plan to Issue

Convert plan/research MD files into GitHub issue body or comments.

## When to Use

- After code-workflow step 2 (plan) to register the plan as a GitHub issue
- When a plan file needs to be shared with the team via GitHub
- When discussion items need to be posted as issue comments

## Procedure

### Step 1: Read Source Material

Read the plan/research file and identify:
- Implementation checklist items
- Verification/test plan
- Open questions / discussion items
- Changed file list

### Step 2: Classify Content → Body vs Comment

| Content | Target | Format |
|---------|--------|--------|
| Implementation checklist | Body | `- [ ]` checkbox list |
| Verification plan | Body | Table: feature / procedure / expected result |
| Changed file summary | Body | Table: file / change description |
| Open questions (undecided items) | **Comment** | Numbered list with context |
| Progress updates | **Comment** | Timestamped note |

### Step 3: Sanitize Internal Paths

**Before writing to GitHub**, strip all internal paths:

| Pattern to Remove | Replacement |
|-------------------|-------------|
| `.ralph/docs/generated/plan-*.md` | (remove entirely or replace with inline content) |
| `.ralph/docs/generated/research-*.md` | (remove entirely) |
| `.ralph/fix_plan.md` | (remove entirely) |
| `.omc/plans/*.md` | (remove entirely) |
| Session IDs, timestamps from fix_plan | (remove entirely) |

### Step 4: Ensure Verification Plan

If the source material lacks a verification plan, **add one before posting**.

Template:
```markdown
### Verification
| Feature | Procedure | Expected Result |
|---------|-----------|-----------------|
| ... | ... | ... |
```

This is a hard requirement — do not post an issue body without verification.

### Step 5: Post to GitHub

**If issue already exists** (`gh issue view <number>`):
1. Body update: `gh issue edit <number> --body "..."`
2. Discussion comment: `gh issue comment <number> --body "..."`

**If issue needs creation**:
1. `gh issue create --title "..." --body "..."`
2. Follow up with discussion comment if needed

### Step 6: Update fix_plan

After posting, update the corresponding fix_plan entry:
- Add issue number reference
- Remove BLOCKED if it was "pending plan review"

## Example

### Input: plan-183-user-access-log.md

Contains:
- Implementation: `recordSystemLog` util + 6 routes
- Verification: 2 test cases
- Open question: none

### Output

**Issue #183 body update** (via `gh issue edit 183 --body "..."`):
```markdown
## Implementation Plan
- [ ] Create `lib/system-log.ts` with `recordSystemLog()`
- [ ] Add log calls to 6 user/authority CRUD routes

## Verification
| Feature | Procedure | Expected |
|---------|-----------|----------|
| CRUD logging | Create user → check /api/system-log | Log entry with INFO level |
| Level filter | Query system-log with level param | Filtered results |
```

(No `.ralph/docs/` paths, no session IDs)

## Rules

- **Issue title must be descriptive** — `fix(web): ...` conventional commit format forbidden. Use prose: "Add retry logic for API calls"
- **H1 is the sole title** — do not add a separate `## Title` section (prevents title duplication)
- **Verification plan required** — do not post an issue body without a Verification section (Step 4)
- **Sanitize internal paths** before posting (Step 3)
