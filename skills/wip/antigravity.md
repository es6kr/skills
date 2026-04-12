# Antigravity WIP Tracking

Track in-session work progress using the `task.md` artifact file.

## Storage

- **Path**: `<appDataDir>/brain/<conversation-id>/task.md`
- **Type**: Artifact (`ArtifactType: "task"`)

## Status Notation

| Notation | Meaning | Description |
|----------|---------|-------------|
| `- [ ]` | **Pending** | Not yet started |
| `- [/]` | **In Progress** | Currently working (only one at a time) |
| `- [x]` | **Completed** | Finished |

## Rendering Rules

> [!IMPORTANT]
> **Do NOT wrap checkboxes in backticks.**
> Some artifact renderers treat backtick-wrapped `[ ]` as inline code, preventing checkbox interactivity. Always use plain markdown checkbox format.

**Correct:**
```markdown
- [ ] Task item
- [/] In progress item
- [x] Completed item
```

**Wrong:**
```markdown
- `[ ]` Task item
- `[/]` In progress item
- `[x]` Completed item
```

## Workflow

### 1. Initialize

Create `task.md` via `write_to_file` with `ArtifactType: "task"`:

```markdown
- [ ] Step 1 description
- [ ] Step 2 description
- [ ] Step 3 description
```

### 2. Progress

Update task status using `replace_file_content`:

```markdown
- [x] Step 1 description
- [/] Step 2 description
- [ ] Step 3 description
```

### 3. Complete

Mark all items as `[x]` when done.

### 4. Add Items

Append new items at the bottom when discovered during work:

```markdown
- [x] Step 1 description
- [/] Step 2 description
- [ ] Step 3 description
- [ ] Step 4 (newly discovered)
```

## Rules

- **One `[/]` at a time** — don't mark multiple items as in progress
- **Update immediately on completion** — mark `[x]` as soon as done
- **No skipping** — proceed in order, don't start next step before completing current
- **Use file edit tools** — use `replace_file_content` or `multi_replace_file_content` to update status, not `write_to_file` (which overwrites the entire file)
