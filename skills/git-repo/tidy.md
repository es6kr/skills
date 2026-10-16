# Repository Tidy Pipeline

High-level orchestrator that reconciles accumulated repository changes, prunes merged worktrees, and systematically extracts clean, isolated topic branches via a 3-stage loop: **prune → commit-tidy → diff-merge**.

## When to use

- After remote PR merges to clean up merged resources and triage remaining dirty changes
- When a local accumulation branch (`local`, `local/ghq`, `wip*`, `scratch*`) contains mixed commits from multiple features
- When working trees accumulate unstaged, uncommitted, or duplicated changes across multiple sessions or agent runs (e.g. Hermes, Ralph)
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
│ Stage 2: Mandatory commit-tidy Invocation (HARD STOP)  │
│ - Inspect remaining dirty changes & unmerged commits   │
│ - Group by domain/component (Anti-Lumping gate)        │
│ - Formulate clean Conventional Commit split plan       │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ Stage 3: diff-merge & Topic Isolation                  │
│ - Resolve active rebase/merge conflict markers         │
│ - Discard redundant chunks already in upstream         │
│ - Create isolated topic worktree & promote to Draft PR │
└────────────────────────────────────────────────────────┘
          │
          ▼
  Are there remaining dirty changes or unmerged topics?
    ├─► YES: Repeat loop from Stage 1 for the next topic
    └─► NO : Repository is clean (Tidy Complete)
```

## Mandatory Gates (HARD STOP)

1. **Mandatory `commit-tidy` Invocation Gate (HARD STOP)**:
   - When dirty changes or multiple unpushed commits exist, bypassing `commit-tidy` by attempting a single monolithic commit or blanket staging is strictly prohibited.
   - The agent MUST invoke `commit-tidy` to analyze file boundaries, separate unrelated features, and establish atomic Conventional Commit definitions.
2. **Accumulation Branch Push Ban**:
   - Accumulation branches (`local`, `local/ghq`, `wip*`, `staging-local`) must NEVER be pushed to remote or proposed for PR directly.
   - Every feature must be extracted to an isolated topic branch (`feat/*`, `fix/*`) cut cleanly from the latest remote base (`origin/main` or `origin/develop`).
3. **Interactive Ask Confirmation Gate**:
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

### Stage 2: Mandatory `commit-tidy` Execution
1. Inspect remaining unpushed commits and dirty working directory files:
   ```bash
   git status -s
   git log --oneline origin/<base>..HEAD
   ```
2. Trigger the `commit-tidy` skill protocol:
   - Categorize files by component, change type, and directory spread.
   - Separate unrelated features (e.g. API vs UI, mail CLI vs orchestration).
   - Formulate atomic commit recommendations with subject + body by default.

### Stage 3: `diff-merge` & Topic Worktree Isolation
1. If merge/rebase conflict markers exist, execute `diff-merge.sh <target_path>`:
   - Present conflict chunks 1:1 in `AskUserQuestion` before editing.
   - Discard accidental reverts or chunks already merged upstream.
2. For each identified topic:
   - Create a dedicated worktree off the clean upstream base:
     ```bash
     git worktree add ".worktrees/<topic-name>" -b <topic-branch> origin/<base>
     ```
   - Cherry-pick or apply only the scoped changes for that topic.
   - Verify unit tests, run security and personal path scans.
   - Push and open a Draft PR (`gh pr create --body-file <path>`).
3. Return to Stage 1 if additional distinct topics or dirty changes remain.
