# Memory Trim

Keep a project memory index (`MEMORY.md`) inside its byte budget by trimming
oversized pointer-line hooks at clause boundaries.

## When to Use

- A hook/reminder reports the memory index is over its byte budget
- `MEMORY.md` grew past ~17KB and sessions load it always-on
- "memory trim", "MEMORY.md compress", "memory index over budget"

## Background

The index holds one line per memory: `- [Title](file.md) — hook`. The hook is
a **recall cue**, not the storage medium — detail lives in the linked file.
When the index exceeds its budget, hooks can be shortened without information
loss as long as the linked file actually holds the detail.

## Procedure

### Step 1: Run the trim script

```bash
python <skill-dir>/scripts/trim-memory-index.py <memory-dir>/MEMORY.md \
  --budget 17100 --line-cap 160 --dry-run   # preview first
python <skill-dir>/scripts/trim-memory-index.py <memory-dir>/MEMORY.md \
  --budget 17100 --line-cap 160             # apply (writes .bak-trim backup)
```

The script only trims `- [Title](file.md) — hook` lines, and only when the
linked file exists with ≥ `--min-file-bytes` (default 300) — a guard that the
detail is preserved somewhere. Cuts land on clause separators and never leave
an unbalanced backtick span.

### Step 2: Handle what the script skips (manual)

| Leftover | Handling |
|----------|----------|
| Inline-content bullets (no linked file) | Move the body into a new memory file (frontmatter: name/description/type) + replace with a 1-line pointer |
| Awkwardly cut hooks | Rewrite the hook by hand within the line cap |
| Linked file too small to hold the hook's detail | Append the detail to the file first, then re-run the script |

### Step 3: Stale entries (user approval required)

Merging or deleting stale/duplicate entries is NOT automated. Enumerate
candidates (orphan files not in the index, outdated point-in-time snapshots,
entries superseded by later decisions) and confirm each deletion with the
user before removing.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Trim a hook whose linked file is missing or tiny | The script skips these; append the detail to the file first |
| 2 | Delete stale entries autonomously to reclaim bytes | Deletion candidates go through user confirmation, every time |
| 3 | Put memory content in the index to "save a file" | Index = one pointer line per memory. Content lives in the memory file |
| 4 | Edit the index without a backup | The script writes `<file>.bak-trim`; keep it until the next session verifies recall quality |
