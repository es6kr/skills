# Repository Tidy Pipeline

High-level orchestrator that reconciles accumulated repository changes, prunes merged worktrees, and systematically extracts clean, isolated topic branches via a 3-stage loop: **prune → temp-rebase-reset uncommitted triage → commit-tidy → diff-merge**.

## When to use

- After remote PR merges to clean up merged resources and triage remaining dirty changes
- When a local accumulation branch (`local`, `local/ghq`, `wip*`, `scratch*`) contains mixed commits from multiple features
- When working trees accumulate unstaged, uncommitted, or duplicated changes across multiple sessions or external agent runs (e.g. Hermes, Ralph)
- When uncommitted changes sit on a stale base branch and direct commit risks duplicate commits or merge divergence
- When uncommitted changes span multiple worktrees and require strict single-branch-at-a-time isolation and deduplication
- Triggered by `/git-repo:tidy`, "repo tidy", "repository tidy", "tidy up worktrees and branches"

## Architecture & Lifecycle Loop

```text
[Accumulation / Dirty Repository]
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ Stage 1: Prune Merged Resources ([prune.md](./prune.md))│
│ - Detect & remove worktrees for merged PRs             │
│ - Remove gone tracking branches                        │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ Stage 2: Rebase-Safe Uncommitted Triage & commit-tidy  │
│ - Temp freeze uncommitted diff (commit -m "temp" ...)  │
│ - Rebase onto latest upstream base (origin/develop)    │
│ - Reset HEAD~1 to restore clean uncommitted diff       │
│ - Eliminate duplicates & group atomic commit units     │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ Stage 3: diff-merge & Topic Worktree Isolation         │
│ - 1-Param: Chunk-level uncommitted triage (Adopt/Drop) │
│ - 2-Param: Worktree deduplication ([IDENTICAL] prune)  │
│ - Create isolated topic worktree & promote to Draft PR │
└────────────────────────────────────────────────────────┘
          │
          ▼
  Are there remaining dirty changes or unmerged topics?
    ├─► YES: Repeat loop from Stage 1 for the next topic (Single-Branch)
    └─► NO : Repository is clean (Tidy Complete)
```

## Mandatory Gates (HARD STOP)

1. **Mandatory `commit-tidy` Invocation Gate (HARD STOP)**:
   - When dirty changes or multiple unpushed commits exist, bypassing `commit-tidy` by attempting a single monolithic commit or blanket staging is strictly prohibited.
   - The agent MUST invoke `commit-tidy` to analyze file boundaries, separate unrelated features, and establish atomic Conventional Commit definitions.
2. **Rebase-Safe Uncommitted Triage Gate (Temp-Rebase-Reset - HARD STOP)**:
   - When uncommitted or untracked changes exist on a working tree, committing them directly on a stale base or relying on `git stash` is strictly prohibited.
   - `git stash` risks losing untracked files, triggers unpredictable merge conflicts during pop, and cannot be traced cleanly in reflog. Direct commits on stale bases create duplicate commits and history divergence.
   - The agent MUST execute the 4-step **Temp-Rebase-Reset-DiffMerge (T-R-R-D)** protocol:
     1. Freeze uncommitted state with a temporary commit (`git add -A && git commit -m "temp: freeze uncommitted changes" --no-verify`),
     2. Rebase onto clean upstream base (`git rebase origin/<base>`),
     3. Mixed reset to restore uncommitted delta (`git reset HEAD~1`),
     4. Triage and prune redundant chunks via `diff-merge.sh`.
3. **Single-Branch Sequential Triage Gate (HARD STOP)**:
   - Triaging multiple dirty worktrees or branches in a blended concurrent batch is strictly prohibited.
   - The agent MUST triage and isolate one branch at a time.
   - When multiple worktrees contain overlapping or identical edits, the agent MUST run `diff-merge.sh <canonical_source> <target_copy> [--auto-clean-identical]` to verify `[IDENTICAL]` status before committing. Redundant duplicate copies must be safely pruned without creating duplicate commits.
4. **Accumulation Branch Push Ban**:
   - Accumulation branches (`local`, `local/ghq`, `wip*`, `staging-local`) must NEVER be pushed to remote or proposed for PR directly.
   - Every feature must be extracted to an isolated topic branch (`feat/*`, `fix/*`) cut cleanly from the latest remote base (`origin/main` or `origin/develop`).
5. **Interactive Ask Confirmation Gate**:
   - Physical deletion of worktrees, branch drops, and commit applications must be confirmed with the user via `AskUserQuestion` at each stage.

## Step-by-Step Procedure

### Stage 1: Prune Merged Resources
1. Run `python skills/git-repo/scripts/prune_merged_worktrees.py --repo <path>` (dry-run).
2. Execute physical cleanup:
   ```bash
   python skills/git-repo/scripts/prune_merged_worktrees.py --repo <path> --execute --delete-branch
   git fetch -p
   ```
3. Report pruned worktrees and reclaimed branch names.

### Stage 2: Rebase-Safe Uncommitted Triage & Mandatory `commit-tidy` Execution

When uncommitted modifications or untracked candidate files exist from background agents (e.g. Hermes, Ralph):

1. **Step 2.1: Safe Freeze with Temp Commit**:
   Freeze the entire working tree state into Git reflog without running pre-commit linters:
   ```bash
   git add -A
   git commit -m "temp: freeze uncommitted working tree changes" --no-verify
   ```
2. **Step 2.2: Rebase onto Clean Upstream Base**:
   Fetch the latest remote base and rebase the temporary commit on top:
   ```bash
   git fetch origin
   git rebase origin/<base>   # e.g. origin/develop or origin/main
   ```
   If 3-way conflicts arise, resolve conflict markers, add resolved files, and run `git rebase --continue`.
3. **Step 2.3: Mixed Reset to Restore Clean Uncommitted Diff**:
   Unstage the temporary commit on the updated base:
   ```bash
   git reset HEAD~1
   ```
   The working directory now reflects the exact uncommitted delta cleanly positioned against the latest upstream base.
4. **Step 2.4: Trigger `commit-tidy` Skill Protocol**:
   - Inspect files via `git status -s` and diffs via `git diff`.
   - Categorize files by component, change type, and directory spread (Anti-Lumping gate).
   - Separate unrelated features (e.g. API vs UI, mail CLI vs orchestration).
   - Formulate atomic commit recommendations with subject + body by default.

### Stage 3: `diff-merge` & Topic Worktree Isolation

1. **Step 3.1: Chunk Triage via `diff-merge.sh` (1-Parameter Mode)**:
   If uncommitted modifications contain ambiguous or overlapping hunks, inspect each hunk against the base:
   ```bash
   bash skills/diff-merge/scripts/diff-merge.sh <worktree_path>
   ```
   - Present conflict chunks 1:1 in `AskUserQuestion` before editing.
   - Discard accidental reverts, stale leftovers, or chunks already merged upstream.
   - Retain only authentic deltas for the target topic.
2. **Step 3.2: Cross-Worktree Deduplication (2-Parameter Mode)**:
   When multiple worktrees share similar changes across parallel agents:
   ```bash
   bash skills/diff-merge/scripts/diff-merge.sh <canonical_source> <target_copy> [--auto-clean-identical]
   ```
   - If `[IDENTICAL]` is detected across all files, discard the duplicate copy worktree directly without authoring redundant commits.
3. **Step 3.3: Topic Worktree Isolation & PR Promotion**:
   For each isolated topic:
   - Create a dedicated worktree off the clean upstream base:
     ```bash
     git worktree add ".worktrees/<topic-name>" -b <topic-branch> origin/<base>
     ```
   - Stage and commit scoped changes via `commit-tidy`.
   - Verify unit tests, syntax, and security scans.
   - Push and open a Draft PR:
     ```bash
     git push -u origin <topic-branch>
     gh pr create --draft --title "..." --body-file <path>
     ```
4. **Step 3.4: Single-Branch Loop Continuation**:
   Return to Stage 1 to process the next dirty branch or worktree sequentially until all uncommitted accumulation is reconciled.
