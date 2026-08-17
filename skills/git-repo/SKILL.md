---
name: git-repo
metadata:
  author: es6kr
  version: "0.1.2"
depends-on:
  - commit-tidy
description: |
  Git repository and SourceGit integration. Topics — clone (ghq), conflict-dry-run (isolated merge test), credential-helper (multi-account HTTPS token), fix-worktree (bare repo recovery), githooks (hook silently never runs — hooksPath precedence, passthrough chain, install trade-off), isolate-hunk (stage own edit amid unrelated content), merge-duplicate, rebase-audit (accidental-revert detection during an active rebase), to-ghq (formerly migrate), to-bare, worktree-register (metadata register/relink), patrol (batch inspect), move-worktree (register/reclaim merged PR), rename-worktree, sourcegit, ssh-key (multi-account SSH map), worktree (inventory + reuse + create), worktree-drift-sync (mirror fix across worktrees safely). Use when: "reuse worktree", "multi-account clone", "Repository not found", "wrong account", "concurrent uncommitted edit", "accidental revert", "githooks ignored", "hook not running", "core.hooksPath", "hook not firing" triggers.
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash(ghq:*)
  - Bash(git:*)
  - Bash(mv:*)
  - Bash(ls:*)
  - Bash(pgrep:*)
  - Bash(cat:*)
---

# Git Repo

Git repository management and SourceGit GUI client integration.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| clone | ghq get with automatic SourceGit registration (multi-account support) | [clone.md](./clone.md) |
| conflict-dry-run | test merge/cherry-pick applicability in an isolated worktree, without touching the main working tree | [conflict-dry-run.md](./conflict-dry-run.md) |
| credential-helper | pin a per-org GitHub token for HTTPS remotes (fixes recurring `Repository not found` from active-account mismatch); HTTPS counterpart to ssh-key | [credential-helper.md](./credential-helper.md) |
| fix-worktree | bare repo worktree configuration recovery | [fix-worktree.md](./fix-worktree.md) |
| githooks | diagnose a `.githooks/` hook that silently never runs (hooksPath precedence, passthrough chains, execute bit) and choose an install method that keeps machine-wide hooks | [githooks.md](./githooks.md) |
| isolate-hunk | stage only your own edit when a tracked file's working tree mixes it with unrelated uncommitted content, via git plumbing (no working-tree changes) | [isolate-hunk.md](./isolate-hunk.md) |
| merge-duplicate | merge duplicate repositories with the same origin | [merge-duplicate.md](./merge-duplicate.md) |
| migrate | **renamed → to-ghq** (backward-compat alias) | [migrate.md](./migrate.md) |
| move-worktree | move/register unregistered worktrees to .claude/worktrees/, reclaim merged PR worktrees | [move-worktree.md](./move-worktree.md) |
| patrol | batch inspection of ghq repositories (status, stash, unpushed + commit-splitter integration) | [patrol.md](./patrol.md) |
| rebase-audit | audit an active interactive rebase's staged files for accidental reverts (HEAD-vs-index diff + revert-pattern heuristic + AskUserQuestion multiSelect) without touching the rebase itself | [rebase-audit.md](./rebase-audit.md) |
| rename-worktree | rename worktree directory and metadata (cross-platform, Windows safe) | [rename-worktree.md](./rename-worktree.md) |
| sourcegit | SourceGit preference.json management (add repos, workspaces, folder rename) | [sourcegit.md](./sourcegit.md) |
| ssh-key | per-repo SSH key mapping for multi-account GitHub (core.sshCommand + IdentityAgent) | [ssh-key.md](./ssh-key.md) |
| to-bare | convert a regular repo → bare + worktree at a custom location, preserving uncommitted changes (inverse of to-ghq; helper: `scripts/repo-to-bare-worktree.sh`) | [to-bare.md](./to-bare.md) |
| to-ghq | migrate bare+worktree → regular `.git` at the ghq path (formerly `migrate`) | [to-ghq.md](./to-ghq.md) |
| worktree | unified worktree acquisition: inventory, reuse inactive, or create new at `.claude/worktrees/` | [worktree.md](./worktree.md) |
| worktree-drift-sync | re-verify each worktree's git state immediately before/after applying an identical fix across a repo's multiple worktrees under external concurrent editing | [worktree-drift-sync.md](./worktree-drift-sync.md) |
| worktree-register | shared: register a populated directory as a worktree via metadata only (used by fix-worktree + to-bare) | [worktree-register.md](./worktree-register.md) |

## Topic Dependencies

```
worktree (entry point — inventory + decision)
  └─→ rename-worktree (reuse registered worktree)
  └─→ move-worktree (register unregistered or relocate)

worktree-register (shared metadata register/relink mechanism)
  ├─← fix-worktree (recover a broken bare-worktree link)
  └─← to-bare (link the working tree after a regular→bare conversion)

to-bare  ←inverse→  to-ghq (formerly `migrate`)

ssh-key (SSH multi-account)  ──counterpart──  credential-helper (HTTPS multi-account)

rebase-audit (active-rebase revert detection)  ──restoration mechanism shared with──  isolate-hunk (targeted hunk staging)
```

## Worktree decision tree (HARD STOP — every time a worktree is needed)

**Whenever a worktree is needed (plan/build/test without switching branches, PR verification, isolated work environment, new commit while main branch has another in-flight task), check for inactive worktree reuse before creating a new one.**

### Flow

1. `git -C <repo> worktree list` to enumerate existing worktrees
2. **Operation-state gate (HARD STOP — before any inactive classification)**: for each candidate worktree `<W>`, check for an in-progress git operation:
   ```bash
   gitdir=$(git -C <W> rev-parse --absolute-git-dir)
   ls "$gitdir"/CHERRY_PICK_HEAD "$gitdir"/MERGE_HEAD "$gitdir"/REBASE_HEAD "$gitdir"/BISECT_LOG "$gitdir"/rebase-merge "$gitdir"/rebase-apply 2>/dev/null
   git -C <W> status --porcelain | grep -E '^(DD|AU|UD|UA|DU|AA|UU)'   # unmerged index entries
   ```
   Any hit = a cherry-pick/merge/rebase/bisect is **mid-flight** (likely the user's active operation) → the worktree is **NOT an inactive candidate**, its dirty files are the operation's payload (never offer discard / `git add` resolution / stash), and reuse is forbidden — report to the user instead. Merge-status heuristics (branch merged + ahead=0) do NOT override this gate. (see failed-attempts.md "cherry-pick in progress misclassified as abandoned")
3. Identify inactive candidates (only among worktrees that passed the gate):
   - **Merged-PR worktrees** (commit hash equals the base branch's merge commit)
   - **Squash-merged-PR worktrees** — see the caveat below; the hash test above does **not** find these
   - **Stale fix/refactor branch worktrees** (confirm with the user)

   **Hash-equality misses every squash merge (HARD STOP)**: a squash merge creates a new single commit on the base with no parent link to the branch, so a worktree whose PR was squashed keeps a HEAD that matches nothing on the base. The test in the first bullet reports it as *not* merged, and its N original commits still read as unmerged work — which both hides a reclaimable worktree and, worse, makes a genuinely stale branch look active. Ask GitHub for the PR state instead of inferring it from hashes:

   ```bash
   B=$(git -C <worktree> branch --show-current)
   gh pr list --head "$B" --state all --json number,state,mergedAt --jq '.[0]'
   ```

   | PR state for the worktree's branch | Classification |
   |------------------------------------|----------------|
   | `MERGED` (regardless of merge method) | Inactive candidate — reclaimable |
   | `OPEN` | Active — not a candidate |
   | `CLOSED` unmerged, or no PR | Stale candidate — confirm with the user before reuse |

   For a `MERGED` squashed branch, reuse means re-pointing the worktree at a fresh branch off the updated base (`rename-worktree`) — do **not** rebase or merge the old branch forward, since its commits duplicate content the base already carries in squashed form.
4. If an inactive worktree exists → **reuse via the `rename-worktree` topic** (rename the directory + metadata, switch branch)
5. If no inactive worktree exists or the user opts for new → `git worktree add`

### New-commit-start trigger (HARD STOP — paired with git.md)

**When committing new work on a main/master/develop branch, if `git status` shows uncommitted changes from another task, worktree splitting is mandatory.**

#### Entry conditions (any one)

- Current branch = main/master/develop
- `git status` shows 1+ changed files outside the new work (e.g., another task's unstaged files)
- Unpushed commits include another task's work

#### Decision tree on entry

```
git status (check for other changes)
  ├─ 0 other changes, branch = PR/feature → commit in place
  ├─ 0 other changes, branch = main/master/develop
  │    → AskUserQuestion: (a) create PR branch from current (b) create PR branch in a new worktree
  ├─ 1+ other changes, branch = main/master/develop
  │    → worktree split required. Leave other changes in place, isolate new work in a new worktree
  └─ Another task running on a PR branch with stray changes on main
       → Report to the user (confirm intent of stray changes) → decide worktree split + stray cleanup
```

#### Worktree split procedure

1. Leave the new work's diff in place — do NOT stash (preserve the working directory)
2. `git -C <repo> worktree list` to inspect inactive worktrees (per the decision tree above)
3. Inactive candidate present → reuse via `rename-worktree`; otherwise `git -C <repo> worktree add .claude/worktrees/<branch>` (or the worktree path defined by the active environment context — see `worktree.md` "Default Path Rules")
4. cd into the new worktree, then `git checkout -b <new-branch>` (or use the existing inactive branch)
5. **Re-apply the same diff in the new worktree via Edit** (the original main changes stay on main)
6. add → commit → push → PR inside the new worktree

#### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | main has other changes; add the new file + commit + push anyway | Run `git status` → if other changes exist → split into a worktree → commit in the new worktree |
| 2 | Hide other changes with `git stash` and commit on main | stash breaks the other task's intent/sequence. Worktree split is safer |
| 3 | Assume "my changes only — no conflict" | Other working-directory changes can spill over (tests, builds, IDE state) |
| 4 | Omit "worktree split" from the AskUserQuestion commit options | If branch is main/master/develop and other changes exist, "split into worktree + create PR branch" must be the first option |

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Default to `git worktree add <path> <branch>` whenever a worktree is needed | `git worktree list` first → check inactive candidates → consider `rename-worktree` |
| 2 | "Temporary verification — create new and delete" pattern (wastes resources) | Reuse a merged-PR worktree (e.g., one stuck at the merge commit) via rename |
| 3 | AskUserQuestion options offer only "create new worktree" | Include "reuse an existing worktree by rename" whenever an inactive worktree exists |
| 4 | Decide on the worktree autonomously before asking the user | When inactive candidates exist, ask which one to reuse |
| 5 | Ignore merged-PR worktrees | Reclaim them with move-worktree or rename-worktree |
| 6 | **Place "create new worktree" as option 1/Recommended when inactive candidates exist** | **Reuse is Recommended/option 1.** New is option 2 or below |
| 7 | "Unknown purpose for the inactive candidate → recommend safe new" thinking | Inspect the inactive candidate state (`git log`, `git status`) first. If still ambiguous, ask the user which to reuse — but keep reuse as option 1 |

### Recommended placement rule (HARD STOP — prevent 2nd recurrence)

**When building AskUserQuestion options for worktree selection**:

| Inactive candidates | Option order + Recommended |
|--------------|------------------------|
| 0 | Option 1: New worktree (Recommended). Option 2: Hold |
| 1 | **Option 1: Reuse inactive by rename (Recommended)**. Option 2: New worktree. Option 3: Hold |
| 2+ | **Option 1: Rename inactive A (Recommended)**. Option 2: Rename inactive B. Option 3: New worktree. Option 4: Hold |

**The Recommended marker must attach to the reuse option.** "Safer to default to new because purpose is unclear" is an autonomous judgment — instead, document the "verify current commit/branch before reuse" procedure in the rename option description so the user can decide.

### Self-check (before any worktree work)

1. Did you call `git -C <repo> worktree list`?
2. **Did you run the operation-state gate (Flow step 2) on every candidate?** A worktree with `CHERRY_PICK_HEAD`/`MERGE_HEAD`/`REBASE_HEAD` or unmerged status codes (DU/UU/AA…) is mid-operation → excluded from candidates, no discard/stash options for its files
3. Does any gated worktree match (a) the same commit as HEAD or (b) a merge commit hash? → inactive candidate
4. If inactive candidates exist, include both the new-add option and the reuse option in AskUserQuestion
5. **Is the Recommended marker attached to the reuse option?** (apply the "Recommended placement rule" table)
6. Use new-add only when 0 inactive candidates exist OR the user explicitly chose new

### Typical failure mode

When a worktree is needed for plan verification, defaulting to "create new + remove later" wastes resources. `git worktree list` often shows merged-PR worktrees stuck on the merge commit hash — these are reuse candidates. Always inventory first before creating a new worktree.

## Quick Reference

### ghq Clone (automatic SourceGit registration)

When `ghq get <url>` is executed, the following happens automatically:
1. Clone the repository
2. Register in SourceGit (under the appropriate group)
3. Auto-create the group if it doesn't exist

**Proceeds automatically without user confirmation**

[Detailed guide](./clone.md)

### SourceGit Management

Directly edit the SourceGit GUI client's configuration file to add repositories, create workspaces, rename folders, etc.

Key features:
- Add/remove repositories
- Create workspaces
- Sync ghq repositories
- Update paths on folder rename

[Detailed guide](./sourcegit.md)

### ghq Migration (to-ghq) / Bare conversion (to-bare)

- **to-ghq** (formerly `migrate`): bare+worktree → regular `.git` at the ghq path (`~/ghq/host/group/repo/`). Auto bare+worktree conversion, optional symlink, nested groups. [Detailed guide](./to-ghq.md)
- **to-bare** (inverse): regular repo → bare + worktree at a custom location (e.g. `.claude/worktrees/`), preserving uncommitted changes. Includes a Windows lock pre-check (SourceGit/VS Code handle on `.git` blocks the rename). [Detailed guide](./to-bare.md)

### Repo Patrol (batch inspection)

Batch inspect and clean up the status of repositories under ghq.

Key features:
- Parallel collection of status, stash, unpushed for all repositories
- Status-based processing (commit-splitter integration, stash pop, push)
- Optional fetch all at the end

[Detailed guide](./patrol.md)

## Common Workflow

1. **Repository migration**: Migrate to ghq structure with `to-ghq` topic (or `to-bare` for the inverse)
2. **SourceGit update**: Register new paths with `sourcegit` topic
3. **Batch inspection**: Clean up uncommitted/unpushed changes with `patrol` topic

## Scripts

- `./scripts/repo-to-ghq.sh` - Move a repository to the ghq path (bare+worktree → regular)
- `./scripts/repo-to-bare-worktree.sh` - Convert a regular repo → bare + worktree (inverse)
- `skills/git-repo/scripts/local-to-staging-pr.sh` - Cherry-pick local commit to a staging branch; prints manual push/PR commands by default, or pass `--push [--body-file <path>]` to also push and open the draft PR.
