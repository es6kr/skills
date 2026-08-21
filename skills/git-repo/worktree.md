# Worktree

Unified workflow for acquiring a git worktree: inventory existing ones, identify inactive candidates, reuse via rename/move, or create new at the default path.

## When to Use

- Need an isolated working directory for a branch (PR verification, plan testing, parallel work)
- Before running `git worktree add` — always check for reusable worktrees first

### 0. Worktree Cap Gate (HARD STOP — Max 10 Worktrees)

Before creating a new worktree, measure total active worktrees:
```bash
git worktree list | wc -l
```
If total count is **10 or more**:
- **New worktree creation is BLOCKED.** Do NOT execute `git worktree add`.
- You MUST either:
  1. Prune/delete merged & inactive worktrees via `git worktree remove <path>`.
  2. Repurpose/reuse an existing inactive/synced worktree via `git checkout -B <new-branch>`.

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

**Step 2.0 — Operation-state gate (HARD STOP, runs before any classification)**: an in-progress git operation disqualifies a worktree from inactive classification regardless of merge status. Check per candidate `<W>`:

```bash
gitdir=$(git -C <W> rev-parse --absolute-git-dir)
for f in CHERRY_PICK_HEAD MERGE_HEAD REBASE_HEAD BISECT_LOG rebase-merge rebase-apply; do
  [ -e "$gitdir/$f" ] && echo "$gitdir/$f"
done
git -C <W> status --porcelain | grep -E '^(DD|AU|UD|UA|DU|AA|UU)'   # unmerged index entries
git -C <W> diff --name-only --diff-filter=U                          # conflicted files
```

Any hit → the worktree is **mid-operation** (cherry-pick/merge/rebase/bisect — likely the user's active surgery):
- It is NOT an inactive candidate; exclude it from reuse/discard options entirely
- Its dirty files are the **operation's payload**, not leftovers — never offer "discard", "stash", or "resolve DU via `git add`" for them
- Report the operation to the user (`MERGE_MSG` names the commit being applied) and let them decide
- **Unmerged status codes (`DU`/`UU`/`AA`/…) in `status --porcelain` always mean an unfinished conflicted operation — never plain dirt.** Treating them as ordinary dirty files is the failure mode (see failed-attempts.md "cherry-pick in progress misclassified as abandoned")

A worktree that passed the gate is **inactive** (reuse candidate) if any of:

| Condition | How to check |
|-----------|-------------|
| Branch was merged and deleted | `git branch -d <branch>` succeeds or remote branch gone |
| Commit hash matches a merge commit on base branch | `git log --oneline <base> \| grep <hash>` |
| Not currently checked out by any session | No editor/terminal has `cwd` in that worktree |
| Stale fix/refactor branch with no recent commits | `git log -1 --format=%ci <branch>` older than 7 days |

### 2.5 Repurposable candidates (synced-to-origin, over-limit fallback)

**Distinct from "inactive" above.** A worktree can have recent activity and an unmerged branch, yet still be safe to repurpose if its branch is **fully pushed to origin** — repointing it to a new branch loses nothing, since the existing work already lives on the remote.

```bash
# For each candidate <W>:
git -C <W> log @{u}..HEAD --oneline   # unpushed commits ahead of the branch's upstream — empty = fully synced
git -C <W> status --porcelain          # empty = no uncommitted local changes either
```

A worktree is **repurposable** when both checks are empty (fully pushed + clean). This is a weaker guarantee than "inactive" (the branch may still be under active review elsewhere), so it is used only as a **fallback** — when the worktree count is over the limit and no §2 inactive candidate exists.

### 3. Decision — reuse or create

**Cost gate first (HARD STOP).** What reuse buys back is a **dependency install / build cache**, not the worktree directory. Where no dependency manifest exists, a fresh worktree is a checkout and nothing more — reuse saves seconds, while renaming a branch destroys whatever intent its name encoded. Classify the repo before consulting the tree:

```bash
ls <repo>/package.json <repo>/pnpm-lock.yaml <repo>/yarn.lock <repo>/Cargo.toml \
   <repo>/go.mod <repo>/pom.xml <repo>/build.gradle <repo>/requirements.txt \
   <repo>/uv.lock <repo>/Gemfile
```

Any hit → **heavy**. No hit → **lightweight** (a docs or shell-skill repo, for instance).

```
repo has a dependency manifest / lockfile?
├─ NO  (lightweight) → Step 4B (new). Reuse is opt-in — offer it only if the user asks.
└─ YES (heavy) ↓
   inactive candidates found?
   ├─ YES → AskUserQuestion: which one to reuse?
   │        ├─ User selects one → Step 4A (rename/move)
   │        └─ User says "create new" → Step 4B (new)
   └─ NO  → worktree count over the limit (see "Inactive Worktree Count Limit")?
            ├─ YES → repurposable candidate found (§2.5)? → oldest one → Step 4A (rename/move)
            │        └─ none found → report to user, ask before creating new
            └─ NO  → Step 4B (new)
```

**In a heavy repo, AskUserQuestion options must include both reuse and new-create** when inactive candidates exist. In a lightweight repo the same offer is noise — new-create is the recommended option, and a branch name that encodes planned intent is preserved rather than renamed.

### 4A. Reuse via rename or move

Delegate to the appropriate sub-topic:

| Situation | Topic |
|-----------|-------|
| Worktree is registered AND already lives under `<repo>/.worktrees/` | [rename-worktree](./rename-worktree.md) — rename dir + metadata + switch branch |
| Worktree dir exists but not registered | [move-worktree](./move-worktree.md) Scenario A — register + switch branch |
| Worktree is registered but its parent directory is NOT `<repo>/.worktrees/` (legacy `.claude/worktrees/`, a sibling dir like `<repo>-wt/`, a bare `~/.worktrees/`, or any other non-canonical path) | [move-worktree](./move-worktree.md) Scenario B — relocate to `<repo>/.worktrees/` **first**, then proceed with the branch switch |

**Path-canonicality applies regardless of which row is taken.** `rename-worktree.sh`'s `--wt-base` flag assumes `<old-name>` already lives directly under that base directory — it renames/re-branches in place, it does not relocate a worktree that lives entirely outside any `--wt-base` tree (e.g. `<repo>-wt/<name>` sitting next to `<repo>/`, or vibe-kanban's own worktree layout). Reusing such a worktree via `rename-worktree.sh` alone perpetuates its wrong location indefinitely — check the parent directory first, and route through Scenario B before renaming when it's not already `<repo>/.worktrees/`.

**Automated pre-check**: `scripts/check-worktree-canonical.sh <repo> <worktree-name-or-path>` performs this parent-directory check mechanically — it exits `0` (canonical — safe to reuse in place), `1` (non-canonical — prints the Scenario B `git worktree move` command to run first), or `2` (not registered — orphan dir, Scenario A). It is detect-only (never mutates a worktree); run it before `rename-worktree.sh` to catch a wrong location without acting on it.

After rename/move, verify:

```bash
git worktree list                    # confirm registration
cd <worktree-path>
git branch --show-current            # confirm target branch
git status --short                   # confirm clean state
```

### 4B. Create new worktree

**Default path**: `<repo>/.worktrees/<branch-name>`

```bash
cd /path/to/repo
git worktree add .worktrees/<branch-name> <branch>
```

If the branch does not exist yet:

```bash
git worktree add -b <new-branch> .worktrees/<new-branch> <start-point>
```

Post-create verification:

```bash
git worktree list
cd .worktrees/<branch-name>
git branch --show-current
```

#### 4B-1. Default `.gitignore` Baseline Gate (HARD STOP)

When standardizing on `<repo>/.worktrees/`, ensuring that `.worktrees/` is ignored in the root repository's `.gitignore` (or `.git/info/exclude`) is **mandatory**. Without this ignore rule, nested worktree trees, dirty edits, and untracked branches will bleed into `git status` in the main repository.

Baseline default `.gitignore` patterns required for every managed repository:

```gitignore
# Runtime & Worktree Isolation
.worktrees/

# OS / Editor Junk
.DS_Store

# Language Caches & Bytecode
__pycache__/

# Backup & Transient Temp Files
*.bak
*.tmp
```

When creating a new worktree or initializing/migrating a repo, verify:

```bash
# Verify .worktrees/ is excluded
grep -q "^\.worktrees/" .gitignore 2>/dev/null || echo ".worktrees/" >> .gitignore
```

### 5. Post-acquisition check (MANDATORY)

Before writing any code in the worktree:

```bash
cd <worktree-path>
git branch --show-current   # must match intended branch
```

If branch mismatch → do NOT proceed with Write/Edit. Fix first (checkout or re-create).

## Commit → worktree → cherry-pick → draft PR (promote local work)

When work accumulates on a local/working branch and needs to land as a reviewable PR, the pattern is: commit on the local branch first, resolve the target base branch, acquire a worktree off that base (reuse-first, per the decision tree above), cherry-pick the commit(s) into it, push, and open a draft PR. Never push the local branch directly, and never move uncommitted changes between branches — commit first, then cherry-pick the commit.

### Steps

1. **Commit on the local/working branch.** The commit is the unit that moves — not the working-tree diff.
2. **Resolve the target base branch.** Two shapes:
   - **Staging-branch model** (a project routes patch-type changes through one staging branch and feature-type changes through another, merging into a longer-lived integration branch later): derive the base from the commit's conventional-commit type. Check whether the target file/directory already **diverges** on a longer-lived staging branch — if so, prefer that staging branch regardless of commit type (see the project's own base-branch resolution rule, if one exists, for the exact divergence check).
   - **Plain-base model** (no staging tier): the base is simply the repo's usual integration branch for the change being made.
3. **Acquire a worktree off the resolved base** — follow the decision tree above (§"Worktree decision tree"): inventory first, reuse an inactive worktree if one exists, otherwise create new off `origin/<base>`.
4. **Cherry-pick the commit(s)** from the local branch into the worktree. On conflict, stop and resolve manually — do not force through.
5. **Push the worktree's branch**, then open a **draft PR** (base = the branch resolved in step 2).

### Automation available

`scripts/local-to-staging-pr.sh <repo-dir> <commit-sha> [--branch <name>] [--base <staging-branch>] [--push [--body-file <path>]]` automates steps 2-4 for repos following the staging-branch model: it derives the base from the commit's conventional-commit tag (override with `--base` for a plain-base repo or a divergence-override case), creates the worktree off `origin/<base>`, cherry-picks, and runs a pre-flight scaffolding check (confirms every directory the commit touches already has its baseline file present on the target base, before creating the worktree). Before creating the worktree, it also runs a **non-interactive** subset of the reuse-first gate (§"Worktree decision tree" Steps 1-3): it reclaims any existing `.claude/worktrees/` entry whose branch is already merged into `origin/main` (safe — no unique commits to lose). It does not implement the full interactive gate for *unmerged* inactive candidates, since that choice requires a human (`AskUserQuestion`); a script cannot make it. By default it stops after a clean cherry-pick and prints the push/PR commands — push and `gh pr create --draft` remain manual, keeping the PR title/body under human review before it goes out. Pass `--push` to also push once you've decided to (same per-invocation call as a bare `git push`), and `--push --body-file <path>` to also open the draft PR from a body you've already authored and reviewed — content authorship still happens before the flag is used, this only automates the ceremony around it.

For plain-base repos (no staging tier), steps 2-5 are manual: run the reuse-first gate (§"Worktree decision tree" Steps 1-3 — inventory, then reuse an inactive worktree if one exists) → `git fetch origin <base>` → worktree add off `origin/<base>` (only if no reuse candidate) → cherry-pick → push → `gh pr create --draft`.

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Push the local/working branch directly to move its commits onto a PR branch | Commit on local first → cherry-pick the commit(s) onto a clean branch off the resolved base → push that branch |
| 2 | Stash or checkout to shuffle *uncommitted* changes onto another branch | Commit first — the commit, not the working-tree diff, is what cherry-picks cleanly |
| 3 | Derive the base purely from the commit's conventional-commit tag when the target file/directory is already known to diverge on a longer-lived staging branch | Check divergence first (e.g. `git diff origin/<default-base> origin/<staging-base> -- <path>`) — a non-empty diff means the staging branch overrides the tag-derived default |
| 4 | Open the PR as ready-for-review by default | Draft is the default for a freshly promoted commit — convert to ready only after the author decides it's reviewable |
| 5 | Resolve the base branch name correctly (step 2), then create/reuse a worktree whose branch ancestry doesn't actually trace to that base (e.g. `git worktree add` off `origin/main` while intending `--base <staging-branch>` at PR-creation time) | Before `git worktree add -b`, run `git log origin/<default-base>..origin/<staging-base> --oneline \| wc -l` (and the reverse) — if both are non-zero, the two branches have diverged and the worktree MUST be created off `origin/<staging-base>` directly, not off `origin/<default-base>` with the base only corrected later at `gh pr create --base`. A resolved base name that doesn't match the worktree's actual git ancestry produces a CONFLICTING PR, discovered only after push |

### Self-check (immediately before `git worktree add` in a staging-branch-model repo)

1. Did step 2 resolve a staging branch (not the plain default base)?
2. If yes, run the mutual-divergence check (`git log origin/<default-base>..origin/<staging-base> --oneline | wc -l` + the reverse direction) **before** `git worktree add` — not after a conflict surfaces
3. Is either count non-zero? → the worktree's start-point must be `origin/<staging-base>`, never `origin/<default-base>`
4. Does the branch about to be passed to `git worktree add -b <branch> <start-point>` have `<start-point>` = the resolved staging branch? Mismatch here is the defect this row prevents, even when the *PR's* `--base` flag is correct

## Default Path Rules

| Environment | Worktree path |
|-------------|--------------|
| Claude Code / Antigravity / Git standard | `<repo>/.worktrees/<name>` |
| vibe-kanban | Managed by vibe-kanban (do not override) |
| Other plugins / agents | Honor the path declared in their context (project `CLAUDE.md`, plugin settings, env var) |

**Default**: this skill standardizes on `<repo>/.worktrees/<name>`.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | `git worktree add` as first action | `git worktree list` first → check for reusable candidates |
| 2 | Present only "create new" in AskUserQuestion | Include "reuse worktree X" option when inactive candidates exist |
| 3 | Create worktree outside `.worktrees/` | Use `.worktrees/` |
| 4 | Start coding without branch verification | `git branch --show-current` before any Write/Edit |
| 5 | Chain `git checkout -b <new> <ref>` immediately followed by `git cherry-pick`/`git reset`/other git commands in a repo with a large pre-existing dirty working tree (e.g. `~/.agents`) | In-place checkout can fail silently ("local changes would be overwritten") while staying on the original branch, so the chained command runs on the wrong branch. Prefer `git branch <new> <ref>` (no working-tree switch) + `git worktree add <path> <new>` from the start when the repo is known to carry unrelated uncommitted content; if in-place checkout is used anyway, verify `git branch --show-current` before the next command (see failed-attempts.md "git-checkout-unverified-chain", 2 occurrences) |
| 6 | Delete inactive worktrees to "clean up" | Reuse them — rename is cheaper than delete+create (subject to count limit below) |
| 7 | Treat unmerged status codes (`DU`/`UU`/`AA`…) as plain dirty files and offer discard/stash/`git add` resolution | Unmerged entries = a conflicted operation is mid-flight (§2 Step 2.0 gate). Exclude the worktree from candidates + report the in-progress operation to the user |
| 8 | Classify "merged + ahead=0 + dirty" as abandoned leftovers | Run the operation-state gate first — a merged branch can host an in-progress cherry-pick applying new work on top |
| 9 | Check multiple state files with one `ls fileA fileB fileC 2>/dev/null \|\| echo "no in-progress op"` call | `ls` returns nonzero if **any** argument is missing, even while printing the paths of the ones that DO exist — a partial hit still fires the `\|\|` fallback and prints a false "no in-progress op" alongside the real hit. Check each file individually (see the operation-state gate command above), and always re-read the raw stdout before trusting a fallback message (see failed-attempts.md "ls multi-arg false negative") |
| 10 | Reuse an inactive worktree via `rename-worktree.sh` (or a manual `git checkout -b` inside it) without checking its parent directory | Before reusing, confirm the worktree's parent directory is already `<repo>/.worktrees/` — if not, relocate via [move-worktree](./move-worktree.md) Scenario B first, then rename/switch branch |
| 11 | Create `<repo>/.worktrees/` without ignoring it in `.gitignore` | Ensure `.worktrees/` and baseline hygiene patterns (`__pycache__/`, `.DS_Store`, `*.bak`, `*.tmp`) exist in `.gitignore` or `.git/info/exclude` |

### Self-check (before reusing or creating any worktree — §3/§4)

1. Is `<repo>/.gitignore` configured to ignore `.worktrees/` and baseline hygiene patterns (`__pycache__/`, `.DS_Store`, `*.bak`, `*.tmp`)?
2. Is the candidate's path already `<repo>/.worktrees/<name>`? Check with `git worktree list` — the path column shows the full location.
3. If not (a legacy `.claude/worktrees/`, a sibling `<repo>-wt/`, a bare `~/.worktrees/`, or anything else) → relocate via move-worktree.md Scenario B **before** renaming/switching branch — do not reuse in place and leave the wrong location to persist across future reuse cycles.
4. Only after the path is confirmed canonical, proceed with rename-worktree.sh or the manual branch switch.

Steps 2-3 can be run mechanically: `scripts/check-worktree-canonical.sh <repo> <candidate-name>` (exit 0 = canonical / 1 = non-canonical, prints the Scenario B move command / 2 = not registered).

## Inactive Worktree Count Limit (HARD STOP)

Reuse via rename is the default for inactive worktrees (Don't/Do rule #5). However, **unbounded reuse accumulation pollutes `git worktree list` and increases the cognitive cost of every future "reuse vs create" decision**. Cap inactive reuse candidates at **5**; beyond that, `git worktree remove` is the correct action.

### Count basis (HARD STOP)

- Count = "inactive" worktrees only (excluding the main worktree at repo root and any currently in-progress feature worktrees the user is actively committing on)
- A worktree is **inactive** by the same criteria as §2 above (no recent commits / merged or deleted branch / dirty stash but no upstream work)
- Active worktrees (claude, currently-edited feature) are **not** counted toward the limit

### Decision matrix

| Repo weight | Inactive count (after cleanup of just-completed worktree) | Action for the just-completed worktree | Rationale |
|-------------|-----------------------------------------------------------|----------------------------------------|-----------|
| **Lightweight** (no dependency manifest — see §3 cost gate) | any | **A: remove** — `git worktree remove <path>` + `git branch -D <feature>` | There is nothing to preserve: a replacement worktree is a plain checkout. Keeping it only grows `git worktree list` and the cost of every future reuse-vs-create decision |
| Heavy | ≤ 5 | **B: reuse** — `git checkout --detach origin/main` + `git branch -D <feature>` | Pool is healthy. What reuse preserves is the installed dependency tree / build cache — that is the actual saving, not the directory |
| Heavy | > 5 | **A: remove** — `git worktree remove <path>` + `git branch -D <feature>` | Pool is full. Removing the just-completed worktree (rather than an older inactive one) avoids touching others' historical workspaces |

**Lightweight repos — removal is offerable at any completion stage.** Once work in a lightweight repo's worktree reaches a completion point — pushed, PR opened, or merged — offering to remove that worktree is appropriate; it need not be held as a reuse candidate. Ask rather than remove silently, since the user may still be reading the diff or expecting review feedback.

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

### Over-limit selection when no inactive candidate exists (HARD STOP)

When the worktree count already exceeds the limit and §2's inactive-candidate check finds none (all branches are unmerged and have recent commits), do **not** default to creating a new worktree or working directly in the main worktree. Apply the repurposable-candidate fallback (§2.5): among worktrees whose branch is fully pushed to origin and synced, **select the oldest one** (by last-commit timestamp) and repurpose it via `/git-repo rename-worktree`.

**Why oldest**: age is the tie-breaker once safety (fully pushed) is established — an older worktree is less likely to represent someone's imminent next action, and "fully pushed" guarantees no data loss regardless of age.

| # | Don't | Do |
|---|-------|----|
| 1 | Conclude "no reuse candidate" once §2's inactive criteria all fail, and default to creating a new worktree or working in the main worktree | Before concluding no candidate exists, run the repurposable check (§2.5) across the worktrees over the limit |
| 2 | Repurpose the newest pushed+synced worktree on the assumption it's "most likely genuinely done" | Select the **oldest** pushed+synced worktree — recency is not a completion signal, only sync status is |
| 3 | Repurpose a worktree with unpushed commits or uncommitted changes just because it's old | Both checks (unpushed commits + uncommitted changes) must be empty — an old-but-dirty worktree is still someone's WIP |

**Self-check (before proposing "no reuse candidate, create new" when over the limit)**:
1. Did §2's inactive check return zero candidates?
2. Is the current worktree count over the limit?
3. If both yes, did you run the repurposable check (§2.5 — unpushed commits + uncommitted changes, both empty) across the existing worktrees?
4. Among repurposable candidates, did you select by **oldest** timestamp, not newest or arbitrary?
5. Only if the repurposable check also finds zero candidates → report this to the user and ask before creating new or working in the main worktree

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
3. Classify each worktree using the same inactive criteria as the **Inactive Worktree Count Limit** section above:
   - **Active**: recent commits look like user's WIP or branch is unfamiliar → halt, report to user
   - **Stale**: branch matches a known merged PR or matches a known stale pattern → safe to ignore
4. If 1+ active worktree found → halt commit, ask the user about that worktree's recent activity
5. Only after all other worktrees classified as Stale → proceed with commit in the target worktree

### Self-check (commit-time, every time)

1. Did you run `git worktree list`?
2. Did you run `git -C <W> log -3` + `status --short` for EACH worktree other than the commit target?
3. Did any other worktree show unfamiliar commits or dirty state?
4. If Yes to #3, did you halt and ask before committing?

**Verdict**: Failing any of items 1-4 = matrix check skipped = rule violation

## Inactive worktree inventory before creating a new one (HARD STOP)

**In a heavy repo, inspect existing worktrees before creating a new one with `git worktree add`.** Run the §3 cost gate first — this inventory obligation applies only where a fresh worktree would cost a dependency install or build.

| # | Don't | Do |
|---|-------|-----|
| 1 | Apply the inventory-first obligation regardless of repo weight | Run the §3 cost gate first. Heavy → inventory first. Lightweight → create new and move on |
| 2 | In a heavy repo, default to creating a new worktree with `git worktree add` whenever one is needed | Run `git worktree list` first → identify inactive / merged-PR worktrees → reuse via `/git-repo rename-worktree` or `/git-repo move-worktree` |
| 3 | In a heavy repo, let AskUserQuestion options default to "create new and remove later" | Include "rename and reuse an inactive worktree" whenever at least one inactive candidate exists |
| 4 | Ignore worktrees pinned at the merge commit of a merged PR (heavy repo) | The base commit hash matching a merge commit = a reuse candidate |
| 5 | In a lightweight repo, surface inactive candidates as if reuse were preferable | Create new. Mention candidates only if the user asks, or to offer removal of ones already finished |

See the "Worktree decision tree" section above for the full procedure.

## Branch state check before starting a new commit (HARD STOP)

**Before committing new work (or before presenting commit-method options via AskUserQuestion), check whether the current branch has uncommitted changes from another task.** When other work is mixed in on a shared branch (main/master/develop), the commit can conflict with that other intent, and `git push` risks conflict/rollback. When detected, **split into a worktree or create a new branch first**.

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Right after Edit, present commit options (PR branch / master push / hold) via AskUserQuestion without checking | Before composing the options, run `git status` — if other-task changes are present, include the "split into worktree" option |
| 2 | Current branch is main/master/develop with unstaged/staged changes; still run `git add <new-file>` | Run `git status` → if changes belong to another task, split via `/git-repo` into a new worktree → commit there |
| 3 | Assume "only my changes are staged, so other changes don't matter" | The same push can include unpushed commits from another task, and other dirty working-directory state can leak into the next step |
| 4 | Omit "split into worktree" from the commit-options AskUserQuestion list | When branch is main/master/develop AND there are 1+ other-task changes, "split into worktree" is a required option |
| 5 | Leave another task's unstaged changes in place and push only the new commit | Confirm the other-task intent (report to the user) → split into a worktree or separate it into another task |
| 6 | **In a heavy repo, place "create new worktree" as option 1 / Recommended when inactive candidates exist** | **In a heavy repo with 1+ inactive candidates, place "rename and reuse" as option 1 / Recommended**; new goes to option 2 or lower. **In a lightweight repo the ordering reverses** — new-create is option 1, because reuse saves nothing there and renaming discards a branch name's intent |
| 7 | Assume "worktree split = move the working-tree changes out of the current repo" (stash + checkout) when the current repo is a live runtime environment whose working tree state is actively consumed by the user (e.g., `~/.agents` — rules are loaded always_on, skills are hardlinked to `~/.claude/skills/`) | Distinguish two split modes: **(a) move** — stash + checkout to a new branch (default for one-off feature work) vs **(b) copy** — leave the source working tree untouched + replicate the diff into a separate worktree via `cp`/`rsync` and commit there. Use (b) whenever the source repo's working tree is a live runtime environment. The source working tree must not change state for the user during commit/PR |

### Self-check (every time before presenting commit options)

1. `git -C <repo> status --short` — list of changed files
2. `git -C <repo> branch --show-current` — current branch
3. Branch is main/master/develop AND ≥2 changes (mine + other) → **worktree split is mandatory**
4. Only my single-task change AND branch is PR/feature → commit in place
5. Unpushed commits present → `git log @{u}..HEAD --oneline` — if another task's commits are mixed in, a separate push strategy is needed

### worktree split decision tree

```text
git status (changes)
  ├─ Only mine (1 task), branch = PR/feature → commit in place
  ├─ Mine + other-task, branch = main/master/develop → /git-repo worktree split mandatory
  ├─ Only mine, branch = main/master/develop → present both "create PR branch in place" and "split into worktree + create PR branch"
  └─ Another task in progress on a PR branch → leave it alone. Return to main and create a new worktree
```

### Failure case

See failed-attempts.md HOT entry "worktree split option missing in commit-method ask".

## `push.default=matching` collateral rejection (repo config gotcha)

Some repos (observed in both `es6kr/skills` and other internal workspace repos) are configured with `push.default=matching` — a bare `git push` (no branch argument) attempts to push **every local branch that has a same-named remote counterpart**, not just the current branch. If any other local branch (e.g., a stale `main` checked out behind in another worktree) is non-fast-forward relative to its remote, the push command reports a `[rejected]` error for that unrelated branch alongside a successful push of the branch you actually intended.

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat a `git push` rejection as failure without checking which branch it refers to | Read the rejection line carefully — it names the specific branch. Confirm your target branch's line shows a successful SHA range (`<old>..<new> branch -> branch`) |
| 2 | Attempt to "fix" the rejected branch (force-push, reset, merge) to silence the warning | The rejected branch is very likely one you weren't working on. Investigate the unexpected branch state before touching it, rather than assuming it needs correcting |
| 3 | Run `git config push.default simple` to "fix" the repo | Changing shared repo config is a user decision — surface the observation, don't silently change config |
| 4 | Keep using bare `git push` in a repo where this has been observed once | Use `git push origin <branch>` explicitly for the rest of the session to avoid repeated collateral noise |

**Detection**: `git config push.default` reports `matching` (default in git before 2.0, still explicitly set in some older repos).

## Branch verification before editing code on issue work (HARD STOP)

**When making a code change tied to an issue number (#N), verify the current branch is the issue's branch BEFORE running Edit/Write.**

| # | Don't | Do |
|---|-------|-----|
| 1 | Editing for #326 while on `feat/222-backchannel-logout` | `git branch --show-current` → issue number mismatch → create the issue branch first |
| 2 | After registering a task via /wip, edit code without verifying branch | Register → `git branch --show-current` → for a github-flow project, ensure issue branch → Edit |
| 3 | "It's a small fix, current branch is fine" thinking | Even a one-line change: a github-flow project requires the issue branch (MEMORY.md reference) |

**Self-check (every time before Edit/Write)**:
1. Does the current branch name include the in-flight issue number?
2. If not, is this project github-flow? (check MEMORY.md)
3. github-flow + issue number mismatch → `gh issue develop --name "<tag>/<issue-number>-<desc>"` or `git checkout -b` first, then work

## Branch verification before implementation in worktree (HARD STOP)

**Before editing code in a worktree via Write/Edit, verify the branch is the intended one.**

The verification timing is **before implementation starts** — not before commit. Once a file is written into the wrong environment, the damage is done.

1. Right after `git worktree add`, **immediately** verify:
   ```bash
   cd "path/to/worktree" && git branch --show-current
   ```
2. If the output does not match the intended branch, **forbid Write/Edit** — re-create the worktree or checkout
3. Starting Write/Edit without this verification = procedural violation

## cd consistency on worktree entry (HARD STOP)

**When the user specifies a worktree path (`.worktrees/<name>` or `.claude/worktrees/<name>`), run every subsequent git command in that worktree directory for the rest of the session.** Forbid `cd` back to the main repo to run git commands — the worktree and the main repo can have **different HEADs**, so `git log HEAD`, `git status`, `git branch --show-current` all return different results.

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Run the first command with `cd <worktree>`, then `cd <main repo> && git fetch ...` on the next | From the first to the last command, stay in the **same worktree only**. Even fetch can run inside the worktree (the `.git` is shared) |
| 2 | "The `.git` is shared between worktree and main, so the results are identical" assumption | Shared `.git` ≠ identical HEAD. Each worktree has its own HEAD/index. `git log HEAD` differs |
| 3 | Ignore that cwd resets between separate Bash calls, and omit `cd` | Add `cd <worktree>` to every Bash call, or use the `git -C <worktree>` flag |
| 4 | Treat `git log origin/develop..HEAD` output as the worktree's commits without verifying where it ran | Before running, check current location via `pwd` or `git rev-parse --show-toplevel`, then report |

### Self-check (before EVERY Bash call during worktree work)

1. The user-specified worktree path = `<W>`
2. Does the Bash command include `cd <W>` or `git -C <W>`?
3. If not, add it. `cd ~/ghq/.../<repo>` (main repo) alone, with no worktree path, is a violation
4. When interpreting command results, self-ask: "is this measured against the worktree or the main repo?"

### Recommended pattern (using the `git -C` flag)

```bash
WT=~/ghq/github.com/<org>/<repo>/.worktrees/fix-18-dev38-launch-url
git -C "$WT" branch --show-current
git -C "$WT" log --oneline origin/develop..HEAD
git -C "$WT" fetch origin develop
```

No cwd change required, no confusion with the main repo.

## Topic Dependencies

```
worktree (this topic — entry point)
  └─→ rename-worktree (reuse registered worktree)
  └─→ move-worktree (register unregistered or relocate)
```
