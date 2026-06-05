# Worktree

Unified workflow for acquiring a git worktree: inventory existing ones, identify inactive candidates, reuse via rename/move, or create new at the default path.

## When to Use

- Need an isolated working directory for a branch (PR verification, plan testing, parallel work)
- Before running `git worktree add` — always check for reusable worktrees first

## Procedure

### 1. Inventory existing worktrees

```bash
cd /path/to/repo
git worktree list
```

Also scan for unregistered worktree directories:

```bash
ls .claude/worktrees/ 2>/dev/null   # Claude Code default path
```

### 2. Identify inactive candidates

A worktree is **inactive** (reuse candidate) if any of:

| Condition | How to check |
|-----------|-------------|
| Branch was merged and deleted | `git branch -d <branch>` succeeds or remote branch gone |
| Commit hash matches a merge commit on base branch | `git log --oneline <base> \| grep <hash>` |
| Not currently checked out by any session | No editor/terminal has `cwd` in that worktree |
| Stale fix/refactor branch with no recent commits | `git log -1 --format=%ci <branch>` older than 7 days |

### 3. Decision — reuse or create

```
inactive candidates found?
├─ YES → AskUserQuestion: which one to reuse?
│        ├─ User selects one → Step 4A (rename/move)
│        └─ User says "create new" → Step 4B (new)
└─ NO  → Step 4B (new)
```

**AskUserQuestion options must include both reuse and new-create** when inactive candidates exist.

### 4A. Reuse via rename or move

Delegate to the appropriate sub-topic:

| Situation | Topic |
|-----------|-------|
| Worktree is registered (`git worktree list` shows it) | [rename-worktree](./rename-worktree.md) — rename dir + metadata + switch branch |
| Worktree dir exists but not registered | [move-worktree](./move-worktree.md) Scenario A — register + switch branch |
| Worktree in wrong location (`.worktrees/`) | [move-worktree](./move-worktree.md) Scenario B — relocate to `.claude/worktrees/` |

After rename/move, verify:

```bash
git worktree list                    # confirm registration
cd <worktree-path>
git branch --show-current            # confirm target branch
git status --short                   # confirm clean state
```

### 4B. Create new worktree

**Default path**: `<repo>/.claude/worktrees/<branch-name>`

```bash
cd /path/to/repo
git worktree add .claude/worktrees/<branch-name> <branch>
```

If the branch does not exist yet:

```bash
git worktree add -b <new-branch> .claude/worktrees/<new-branch> <start-point>
```

Post-create verification:

```bash
git worktree list
cd .claude/worktrees/<branch-name>
git branch --show-current
```

### 5. Post-acquisition check (MANDATORY)

Before writing any code in the worktree:

```bash
cd <worktree-path>
git branch --show-current   # must match intended branch
```

If branch mismatch → do NOT proceed with Write/Edit. Fix first (checkout or re-create).

## Default Path Rules

| Environment | Worktree path |
|-------------|--------------|
| Claude Code (any) | `<repo>/.claude/worktrees/<name>` |
| vibe-kanban | Managed by vibe-kanban (do not override) |
| Other plugins / agents | Honor the path declared in their context (project `CLAUDE.md`, plugin settings, env var) |

**Default**: this skill standardizes on `<repo>/.claude/worktrees/<name>`. If the active environment context (project `CLAUDE.md`, plugin settings such as vibe-kanban, or environment variables) pins a different worktree path, honor that path instead. Creating `<repo>/.worktrees/` ad hoc — without any environment context declaring it — is discouraged because it splinters the worktree root across tools.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | `git worktree add` as first action | `git worktree list` first → check for reusable candidates |
| 2 | Present only "create new" in AskUserQuestion | Include "reuse worktree X" option when inactive candidates exist |
| 3 | Create worktree in `.worktrees/` | Use `.claude/worktrees/` |
| 4 | Start coding without branch verification | `git branch --show-current` before any Write/Edit |
| 5 | Delete inactive worktrees to "clean up" | Reuse them — rename is cheaper than delete+create (subject to count limit below) |

## Inactive Worktree Count Limit (HARD STOP)

Reuse via rename is the default for inactive worktrees (Don't/Do rule #5). However, **unbounded reuse accumulation pollutes `git worktree list` and increases the cognitive cost of every future "reuse vs create" decision**. Cap inactive reuse candidates at **5**; beyond that, `git worktree remove` is the correct action.

### Count basis (HARD STOP)

- Count = "inactive" worktrees only (excluding the main worktree at repo root and any currently in-progress feature worktrees the user is actively committing on)
- A worktree is **inactive** by the same criteria as §2 above (no recent commits / merged or deleted branch / dirty stash but no upstream work)
- Active worktrees (claude, currently-edited feature) are **not** counted toward the limit

### Decision matrix

| Inactive count (after cleanup of just-completed worktree) | Action for the just-completed worktree | Rationale |
|-----------------------------------------------------------|----------------------------------------|-----------|
| ≤ 5 | **B: reuse** — `git checkout --detach origin/main` + `git branch -D <feature>` | Pool is healthy. Reuse avoids the cost of fresh worktree creation (~10-30s + ENOSPC risk on small `.git/worktrees`) |
| > 5 | **A: remove** — `git worktree remove <path>` + `git branch -D <feature>` | Pool is full. Removing the just-completed worktree (rather than an older inactive one) avoids touching others' historical workspaces |

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Keep every just-completed worktree as a reuse candidate regardless of count | Apply the matrix above; remove beyond 5 inactive |
| 2 | Choose A (remove) when inactive count is ≤ 5 to "be tidy" | Reuse is cheaper than create. B is default until the cap is hit |
| 3 | Remove an *older* inactive worktree to make room for the just-completed one | Remove the **just-completed** one. Older inactive worktrees may have stashes / unpushed branches worth preserving |
| 4 | Count active worktrees (claude, in-progress feature) toward the limit | Active = currently used. Only inactive worktrees count |

### Self-check (every time after a worktree's branch is merged/deleted)

1. Run `git worktree list` → count entries excluding repo root + active worktrees
2. If count > 5 after this just-completed worktree → choose A (remove)
3. If count ≤ 5 → choose B (detach + branch -D) for reuse
4. Always pull main worktree to `origin/main` regardless of A or B

### Origin

User decision 2026-05-24 after PR #160 merge cleanup of `agent-abbddf41` worktree (8 total worktrees, 5 inactive after cleanup — at the limit, B chosen). Rule extracted from the trade-off between "rename is cheaper than delete+create" (existing Don't/Do #5) and "unbounded accumulation pollutes the worktree list".

## Pre-commit worktree matrix check (HARD STOP)

**Before starting any new commit (in any worktree, including the main repo), inspect the entire worktree matrix to confirm no other worktree has active in-flight work the user is still arranging.** Failing this check leads to "the user was reorganizing another worktree and I committed without noticing" — a high-cost recovery (sometimes amend/rebase, sometimes user objection).

**Why**:
- `git worktree list` shows commit hash per worktree but not staged/dirty state. A worktree may have active commits the user just authored or is staging
- The user may be mid-cleanup across multiple worktrees in parallel (e.g., reorganizing inactive worktrees while you commit in the main). Your commit collides with their intent
- Worktree commit hash equal to a merge commit on a published branch does NOT mean inactive — it could be a freshly checked-out reuse target the user is preparing

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | `git worktree list` only checks commit hash, skip per-worktree state inspection | For each worktree, run `git -C <path> log -3 --oneline` + `git -C <path> status --short` before commit |
| 2 | Trust "worktree branch is not my work branch, so it's safe" | Other worktree's branch may carry user's WIP. Read its recent commits + dirty state |
| 3 | Skip the matrix check when committing on main/master/develop | Especially required on shared branches — multiple worktrees may share dependent state |
| 4 | "User said the main is clean, so all worktrees are clean" | User may be focused on one worktree. Matrix check covers all worktrees regardless |
| 5 | After the check, commit without noting unfamiliar worktrees | If a worktree's branch/commits are unfamiliar, ask the user about that worktree's purpose before committing in another worktree |

### Procedure (before EVERY commit)

1. `git worktree list` — enumerate paths + branches + commit hashes
2. For each worktree path `<W>` other than the current commit target:
   - `git -C <W> log -3 --oneline` — recent commits in that worktree's branch
   - `git -C <W> status --short` — dirty / staged state
3. Classify each worktree:
   - **Active**: recent commits look like user's WIP or branch is unfamiliar → halt, report to user
   - **Stale**: branch matches a known merged PR or matches a known stale pattern → safe to ignore
4. If 1+ active worktree found → halt commit, ask the user about that worktree's recent activity
5. Only after all other worktrees classified as Stale → proceed with commit in the target worktree

### Self-check (commit-time, every time)

1. Did you run `git worktree list`?
2. Did you run `git -C <W> log -3` + `status --short` for EACH worktree other than the commit target?
3. Did any other worktree show unfamiliar commits or dirty state?
4. If Yes to #3, did you halt and ask before committing?
5. Failing any of items 1 through 4 = matrix check skipped = rule violation

## Topic Dependencies

```
worktree (this topic — entry point)
  └─→ rename-worktree (reuse registered worktree)
  └─→ move-worktree (register unregistered or relocate)
```
