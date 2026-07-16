# Claude Code Memory Dual-Sync (Windows ↔ WSL)

Claude Code uses different project memory paths depending on the runtime environment (Windows / WSL). When saving or editing memory, **both paths must be updated** so that sessions in either environment see the same memory.

## Path Mapping Rules

| Environment | Project Key Pattern | Memory Path |
|------|-----------------|------------|
| WSL | `-mnt-c-Users-{USER}-{rest}` | `~/.claude/projects/-mnt-c-Users-{USER}-{rest}/memory/` |
| Windows | `c--Users-{USER}-{rest}` | `/mnt/c/Users/{USER}/.claude/projects/c--Users-{USER}-{rest}/memory/` |

Example (turborepo-web):
- WSL: `/home/dgs/.claude/projects/-mnt-c-Users-DAEGUNSOFT-ghq-github-com-daegunsoftDev-turborepo-web/memory/`
- Windows: `/mnt/c/Users/DAEGUNSOFT/.claude/projects/c--Users-DAEGUNSOFT-ghq-github-com-daegunsoftDev-turborepo-web/memory/`

## Sync Procedure

1. **New memory file**: Write to both paths
2. **Modify existing memory**: **Edit** both paths (do not overwrite with Write)
3. **MEMORY.md index**: keep identical on both sides
4. **If the counterpart path is missing the file**: Write a fresh copy (sync correction)

## vibe-kanban Worktree Memory (Volatile)

When running inside a vibe-kanban worktree (`~/.local/Temp/vibe-kanban/worktrees/`), the Claude Code project key is generated from the **temporary path** (e.g., `C--Users-DAEGUN-1-AppData-Local-Temp-vibe-kanban-worktrees-...`).

- Memory under that path becomes **orphaned and effectively lost** when the worktree is deleted
- When saving memory inside a worktree session, always write to the **main project memory path**

```
# Worktree memory (X — volatile)
~/.claude/projects/C--Users-DAEGUN-1-AppData-Local-Temp-vibe-kanban-worktrees-.../memory/

# Main project memory (O — persistent)
~/.claude/projects/c--Users-{USER}-ghq-github-com-{org}-{repo}/memory/
```

- Ignore auto-generated `MEMORY.md` under the worktree path; Write/Edit only the main path
- Dual-sync (Windows ↔ WSL) applies to the main path

## Hardlink Paths — No Sync Needed

**`~/.agents/skills/` and `~/.claude/skills/` are hardlinks.** Same applies to `~/.agents/rules/` and `~/.claude/rules/`.

- Edit/Write on one side is automatically reflected on the other (same inode)
- **No manual dual-sync** — `cp`, `rsync`, or editing both sides are all unnecessary
- Verify: `stat -f "%i" <pathA> <pathB>` — same inode = hardlink
- Applies to: `skills/`, `rules/` (other directories: verify case by case)

## Prohibited

- Editing one side and forgetting the other
- Using Write on existing files (overwrites edits made on the counterpart)
- Hardcoding without path mapping (apply the pattern when a new project is added)
- Saving memory only under the worktree temp path without mirroring to the main path
