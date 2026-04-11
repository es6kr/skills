---
name: git-repo
depends-on: [commit-tidy]
description: Git repository and SourceGit integration management. clone - ghq get with automatic SourceGit registration [clone.md], fix-worktree - bare repo worktree configuration recovery [fix-worktree.md], merge-duplicate - merge duplicate repositories with the same origin [merge-duplicate.md], migrate - migrate repositories to ghq structure [migrate.md], patrol - batch inspection of ghq repositories [patrol.md], sourcegit - SourceGit preference.json management [sourcegit.md]. "ghq get", "ghq clone", "sourcegit", "ghq migrate", "repo migrate", "folder rename", "repo patrol", "ghq inspect", "check all repos", "git batch inspect", "duplicate repo", "repo merge", "worktree fix", "bare convert", "multi-account clone" triggers
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
| fix-worktree | bare repo worktree configuration recovery | [fix-worktree.md](./fix-worktree.md) |
| merge-duplicate | merge duplicate repositories with the same origin | [merge-duplicate.md](./merge-duplicate.md) |
| migrate | migrate regular Git repositories to ghq directory structure | [migrate.md](./migrate.md) |
| patrol | batch inspection of ghq repositories (status, stash, unpushed + commit-splitter integration) | [patrol.md](./patrol.md) |
| sourcegit | SourceGit preference.json management (add repos, workspaces, folder rename) | [sourcegit.md](./sourcegit.md) |

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

### ghq Migration

Migrate regular Git repositories to ghq directory structure (`~/ghq/host/group/repo/`).

Key features:
- Automatic bare+worktree structure conversion
- Create symbolic links at original location
- Nested group support (host/group/subgroup/repo)

[Detailed guide](./migrate.md)

### Repo Patrol (batch inspection)

Batch inspect and clean up the status of repositories under ghq.

Key features:
- Parallel collection of status, stash, unpushed for all repositories
- Status-based processing (commit-splitter integration, stash pop, push)
- Optional fetch all at the end

[Detailed guide](./patrol.md)

## Common Workflow

1. **Repository migration**: Migrate to ghq structure with `migrate` topic
2. **SourceGit update**: Register new paths with `sourcegit` topic
3. **Batch inspection**: Clean up uncommitted/unpushed changes with `patrol` topic

## Scripts

- `./scripts/repo-to-ghq.sh` - Script to move repositories to ghq path
