---
metadata:
  author: es6kr
  version: "0.1.1"
name: commit-tidy
depends-on:
  - cleanup
  - git-repo
description: |
  Analyze staged/committed changes and recommend split, squash, or commit-message strategy.
  Topics — hunk-split (non-interactive single-hunk staging via git apply --cached when git add -p isn't usable),
  interactive-amend (worktree-based amend+rebase loop),
  soft-reset-amend (soft-reset top N + selective re-commit),
  staging-discipline (`git diff --cached --name-only` audit + sensitive-dir gate for rules/agents/docs),
  security-scan (PUBLIC repo 4-grep secret pattern check before commit),
  message-discipline (Conventional Commit tags, PUBLIC English enforcement, operation-type continuity, --amend refresh, source-code .md behavior verbs).
  Use when: "commit split", "squash commits", "tidy commits", "amend earlier", "interactive amend",
  "soft reset", "rewrite commits", "PUBLIC repo commit", "secret in commit", "commit message",
  "commit author identity", "commit message English", "staging discipline", "hunk split",
  "stage one hunk", "git apply --cached", "non-interactive git add -p".
---

# Commit Tidy

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| hunk-split | Non-interactive single-hunk staging via `git apply --cached` when `git add -p` isn't usable | [hunk-split.md](./hunk-split.md) |
| interactive-amend | Worktree-based amend+rebase loop for earlier/multiple commits | [interactive-amend.md](./interactive-amend.md) |
| message-discipline | Commit message conventions — Conventional Commit tags, PUBLIC English enforcement, --amend refresh, source-code .md behavior verbs, operation-type continuity | [message-discipline.md](./message-discipline.md) |
| security-scan | PUBLIC repo commit body 4-grep secret pattern check (PAT/Vault/API key/Base64) before commit | [security-scan.md](./security-scan.md) |
| soft-reset-amend | Soft-reset top N commits and selectively re-commit (simpler than worktree rebase) | [soft-reset-amend.md](./soft-reset-amend.md) |
| staging-discipline | `git diff --cached --name-only` audit + sensitive-dir gate (rules/agents/docs) before commit | [staging-discipline.md](./staging-discipline.md) |

Analyze staged/unstaged changes and recommend whether to split into multiple commits.

## When to use

- Before committing large changesets
- User asks "should I split this commit?"
- Reviewing changes that touch many files
- Ensuring atomic, reviewable commits

## Mandatory Invocation Gate (HARD STOP)

- **5+ Files / Large-Scale Modification Gate**: Whenever 5+ files are modified/added/deleted, or a broad cross-directory refactoring, skill renaming, or multi-component edit occurs, invoking `commit-tidy` before committing is **MANDATORY** (`HARD STOP`). Monolithic single-commit attempts without a commit-tidy split & staging review are strictly prohibited.

## Squash-scan scope (HARD STOP)

**A user-named commit range is the minimum scope, never the maximum.** The moment any squash candidate is found — whether self-discovered or pointed at by the user — scan the *entire* unpushed range (`git log --name-only @{u}..HEAD`) grouped by file for the same repeated-single-file pattern before proposing a squash plan. See `staging-discipline.md` "Full-range squash-candidate scan" for the procedure. Presenting a squash plan for only the range the user mentioned, while an identical streak sits elsewhere in the same unpushed history, is a violation — the assistant surfaces the full picture, not just the part the user already knew about.

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

## Reset & Rollback Commit Tidy Rule (HARD STOP)

- **Mandatory Amend on Rollback**: When recovering initial configurations or adding files after a repository reset/rollback to the Initial Commit state, do not accumulate new commits; **always merge changes into the existing initialization commit via `git commit --amend`**.
- **Clean Single Initial Commit**: Organize initial repository setups (`CLAUDE.md`, `index.md`, `log.md`, `pages/`) into a single clean, self-contained initial commit to maximize history readability.

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
Subject: test(dt): add OIDC auth unit tests
Body:
  Consolidates OIDC unit tests from the prior per-loop splits — covers the
  auth flow, proxy interaction, SSO behavior, and route handlers
  (login / callback / me) in a single coherent test commit.

**Reasoning**: Same type (test), same feature (OIDC auth), agent loop split
```

The body in every recommended commit follows `message-discipline.md` "Default commit message structure" — body is recommended by default, free-form (not restricted to per-file enumeration), footer optional.

## Instructions

### Step 0: Determine scope

When ARGUMENTS specify a range (e.g., "since main", "last 3 commits", "PR #N"), analyze **all changes in that range** — both committed and uncommitted.

```bash
# Range specified (e.g., "X changes since main")
git log --oneline <base>..HEAD -- <path>     # committed changes
git diff <base>..HEAD --stat -- <path>        # committed diff
git diff HEAD --stat -- <path>                # uncommitted diff
```

The analysis must cover **committed commits (squash/split candidates) + uncommitted changes (new commit candidates)** as a single unified view. Do not analyze only uncommitted changes when a range is specified.

When no range is specified, default to staged + unstaged changes only.

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

Provide specific recommendations. **Every recommended commit includes a body by default** (see `message-discipline.md` "Default commit message structure"). The body is free-form — it does not have to enumerate per-file changes.

**Mandatory Interactive Ask Gate (HARD STOP)**: Autonomous commit execution or git push without user confirmation is STRICTLY FORBIDDEN. After presenting the split/squash recommendation, you MUST present the split options to the user via `AskUserQuestion` to obtain explicit approval before executing any `git commit` or `git push`. Even when `git pull --rebase` is required or executed, automatically running `git push` afterwards is strictly forbidden without a new `AskUserQuestion` confirmation.

```
## Analysis Results

### Changed Files (N files)
- src/api/... (3 files) - API endpoints
- src/components/... (2 files) - UI components
- tests/... (2 files) - Tests

### Recommendation: Split into N commits

**Commit 1**:
  Subject: feat: add user profile API
  Body:
    Adds POST /users/profile and GET /users/profile/:id endpoints backed by a
    shared validation schema. Both endpoints reuse the existing auth middleware
    and return consistent error shapes. Unit tests cover happy path plus
    validation-error branches.
  Footer (optional): Closes #<issue>
  Files:
    - src/api/user.ts
    - src/api/types.ts
    - tests/api/user.test.ts

**Commit 2**:
  Subject: feat: add profile UI component
  Body:
    Adds a Profile component that consumes the new API endpoints, including
    loading and error states. CSS extracted into a sibling module to keep the
    component file focused on behavior. Component tests stub the API client to
    exercise the loading / success / error branches independently.
  Files:
    - src/components/Profile.tsx
    - src/components/Profile.css
    - tests/components/Profile.test.tsx

### Reasoning
- API and UI can function independently
- Each can be reviewed by different reviewers
```

### Step 4.5: Local commit-type rule self-check (HARD STOP — before Step 5)

**Before executing the recommended split, run the working-tree-specific commit-type override self-check.** Workspaces with `<repo>/.claude/rules/*.md` defining their own commit-type / version-bump mapping take precedence over the global tag-selection defaults applied in Step 4.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
find "$REPO_ROOT/.claude/rules/" -name '*.md' 2>/dev/null
```

If the find returns one or more files, grep them for commit-type semantics (recursive to match the `find` scope above):

```bash
grep -rliE 'commit type|conventional commit|version bump|feat|fix|topic' \
  "$REPO_ROOT/.claude/rules/" --include='*.md' 2>/dev/null
```

Read each matched file. If a local mapping exists (e.g., "new topic = `feat:`, in-place edit of existing topic = `fix:`"), **re-classify each recommended subject under the local mapping before invoking Step 5**. Example reclassification:

| Step 4 draft (global default) | Local rule | Step 5 subject |
|------------------------------|-----------|----------------|
| `feat(skill-X): add HARD STOP for Y` (no new topic file) | `branch-policy.md` "in-place edit = `fix:`" | `fix(skill-X): require Y` |
| `feat(skill-X): add new-topic.md` (new topic file present) | same rule | `feat(skill-X): add new-topic topic` (unchanged) |

See `message-discipline.md` → "Working-tree-specific commit-type override (HARD STOP)" for the full self-check.

### Step 4.6: Prior-merge regression check (HARD STOP — before presenting the split as ready)

**Before declaring a split "confirmed / ready to execute", check whether any staged file's skill was already the subject of a merged PR — especially a squash-merged one.** A squash-merge collapses individual commits (including "address review findings" fix commits) into one commit on the base branch. Staged changes that touch the same files can silently regress a bug that a findings-application commit already fixed, and a structural/pattern-scan diff will not reveal it.

```bash
# has this skill already got a merged PR? (repo-specific owner/repo)
gh pr list -R <owner>/<repo> --state merged --search "<skill-name>" --json number,title,mergedAt,baseRefName

# resolve the actual base (do not assume origin/main — staging repos use next-feat/next-fix)
gh pr view <N> -R <owner>/<repo> --json baseRefName -q '.baseRefName'

# if the PR had multiple commits before merge, list them — findings-application
# commits are recognizable by "review findings" / "internal review" / "address feedback"
gh api repos/<owner>/<repo>/pulls/<N>/commits --jq '.[] | {sha: .sha[0:7], message: .commit.message}'
```

Diff the staged content against the **actual resolved base ref** (not an assumed default) — and read the **full** diff, not a `head -N` or `grep`-filtered slice:

```bash
git diff origin/<actual-base> -- <file>
```

For any hunk that overlaps a findings-application commit's touched lines, and for any changed logic that is testable (regex assignment, conditional branch, script behavior), **execute the changed line(s)** to confirm behavior — a diff read is not a substitute for running the code.

| # | Don't | Do |
|---|-------|----|
| 1 | Conclude "purely additive, no regression" from `grep -E '^\+##'` / `head -100` pattern-scan of a diff | Read the full diff line by line; treat any hunk overlapping a findings-application commit's region as requiring explicit re-verification |
| 2 | Diff staged changes against `origin/main` when the actual PR base was a staging branch (`next-feat`/`next-fix`) | Resolve the actual merge base via `gh pr view --json baseRefName` first, then diff against that ref |
| 3 | Declare "no regression" without executing/testing the changed logic | Run the actual code path (`bash -c`, a grep match test, a unit test) before asserting correctness |
| 4 | Present a split as "confirmed / ready to execute" before this check has run on every touched skill | This check is part of split-readiness — gate Step 5 (and any user-facing "ready" claim) on it passing |

### Step 5: Execute split (if requested)

Use HEREDOC (`git commit -F -`) so the body and optional footer land in the commit message exactly as drafted. Per `message-discipline.md`, single `-m "<subject>"` invocations are reserved for the rare subject-only acceptable cases (typo / routine dep bump).

```bash
# Unstage all
git reset HEAD

# Stage first commit files
git add src/api/ tests/api/
git commit -F - <<'EOF'
feat: add user profile API

Adds POST /users/profile and GET /users/profile/:id endpoints backed by a
shared validation schema. Both endpoints reuse the existing auth middleware
and return consistent error shapes. Unit tests cover happy path plus
validation-error branches.
EOF

# Stage second commit files
git add src/components/ tests/components/
git commit -F - <<'EOF'
feat: add profile UI component

Adds a Profile component that consumes the new API endpoints, including
loading and error states. CSS extracted into a sibling module to keep the
component file focused on behavior. Component tests stub the API client to
exercise the loading / success / error branches independently.
EOF
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
4. Suggested commit messages for each — **subject + body by default** (free-form body, footer optional). See `message-discipline.md` "Default commit message structure". Subject-only is reserved for typo / routine dep bump
5. Per-commit body draft — free-form prose / bullets / sections, NOT restricted to per-file enumeration
6. Execution commands (if requested) — use `git commit -F - <<'EOF'…EOF` HEREDOC form so the drafted body / footer lands in the commit message verbatim
