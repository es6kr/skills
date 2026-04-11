---
name: commit-tidy
description: Analyze staged/committed changes and recommend splitting or squashing strategy. Use when the user says "commit split", "split commits", "should I split this commit", "squash commits", "tidy commits", or when reviewing large changesets before committing.
---

# Commit Tidy

Analyze staged/unstaged changes and recommend whether to split into multiple commits.

## When to use

- Before committing large changesets
- User asks "should I split this commit?"
- Reviewing changes that touch many files
- Ensuring atomic, reviewable commits

## Split Decision Criteria

### Split when

1. **Unrelated functionality changes**
   - Feature A + Bug fix B → 2 commits
   - UI change + API change (if independent) → 2 commits

2. **Wide file spread**
   - Changes span 5+ directories with no common purpose
   - Frontend + Backend + Config all modified

3. **Mixed change types**
   - Refactoring + New feature → 2 commits
   - Formatting + Logic change → 2 commits
   - Dependency update + Code change → 2 commits

4. **Large diff size**
   - 500+ lines changed across unrelated areas
   - Multiple components modified independently

5. **Different reviewers needed**
   - Changes require different domain expertise
   - Security-sensitive + general changes

### Keep together when

1. **Single logical change**
   - Feature requires touching multiple files
   - Refactoring that must be atomic

2. **Dependent changes**
   - API change + caller updates
   - Schema change + migration + model update

3. **Related cleanup**
   - Feature + directly related tests
   - Bug fix + regression test

## Squash Criteria

When analyzing multiple commits, **recommend squashing as well as splitting**.

### Squash when

1. **Same type + same purpose**
   - `test: A test` + `test: B test` (tests for the same feature) → squash into 1
   - `fix: typo A` + `fix: typo B` (same review feedback) → squash into 1

2. **Commits split per loop by automated agents**
   - Autonomous agents like Ralph commit per loop → squash if same purpose
   - Example: proxy test in loop 1, OIDC test in loop 2 → `test: add unit tests`

3. **Consecutive WIP commits**
   - `wip: in progress` + `feat: complete` → squash into one feat

### Don't squash

1. **Commits with different types** — keep `test` + `chore` + `feat` separate
2. **Commits belonging to different PRs/issues**
3. **Independent changes that may need to be reverted**

### Output format (when recommending squash)

```
### Recommendation: Squash 2 commits → 1

**Before** (2 commits):
- 441b966a test(dt): OIDC auth, proxy, SSO tests
- e2b6503a test(dt): OIDC route tests (login, callback, me)

**After** (1 commit):
- test(dt): add OIDC auth unit tests

**Reasoning**: Same type (test), same feature (OIDC auth), agent loop split
```

## Instructions

### Step 1: Analyze changes

```bash
# Check staged changes
git diff --cached --stat
git diff --cached --name-only

# Check unstaged changes
git diff --stat
git status
```

### Step 2: Categorize files

Group changed files by:
- **Feature/Component**: Which feature does this belong to?
- **Change type**: feat, fix, refactor, style, test, docs, chore
- **Directory**: Are changes localized or spread out?

### Step 3: Identify boundaries

Look for natural split points:
- Different conventional commit types
- Independent functionality
- Separate test files from implementation (if tests are for different features)

### Step 4: Recommend split strategy

Provide specific recommendations:

```
## Analysis Results

### Changed Files (N files)
- src/api/... (3 files) - API endpoints
- src/components/... (2 files) - UI components
- tests/... (2 files) - Tests

### Recommendation: Split into N commits

**Commit 1**: feat: add user profile API
- src/api/user.ts
- src/api/types.ts
- tests/api/user.test.ts

**Commit 2**: feat: add profile UI component
- src/components/Profile.tsx
- src/components/Profile.css
- tests/components/Profile.test.tsx

### Reasoning
- API and UI can function independently
- Each can be reviewed by different reviewers
```

### Step 5: Execute split (if requested)

```bash
# Unstage all
git reset HEAD

# Stage first commit files
git add src/api/ tests/api/
git commit -m "feat: add user profile API"

# Stage second commit files
git add src/components/ tests/components/
git commit -m "feat: add profile UI component"
```

## Quick Reference

### File spread heuristic

| Files | Directories | Recommendation |
|-------|-------------|----------------|
| 1-5 | 1-2 | Usually single commit |
| 5-10 | 2-3 | Review for split |
| 10+ | 4+ | Likely needs split |

### Change type combinations to split

| Combination | Split? |
|-------------|--------|
| feat + feat (unrelated) | ✅ Yes |
| feat + related test | ❌ No |
| fix + unrelated refactor | ✅ Yes |
| refactor + style (same files) | ❌ No |
| chore(deps) + feat | ✅ Yes |

## Output Format

Analysis results should include:

1. List of changed files with categories
2. Whether split is needed and why
3. Specific commit splitting plan
4. Suggested commit messages for each
5. Execution commands (if requested)
