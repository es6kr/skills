# Antigravity WIP Tracking

> ⚠️ **STALE — needs verification (flagged 2026-07-06).** The "AskUserQuestion emulation via `ask.md`" guidance below was written when the Antigravity agent had **no** native `AskUserQuestion` tool. Per the user, Antigravity **later added a native `AskUserQuestion` tool** (distinct from the Gemini CLI, which still lacks it). Before relying on the `ask.md` emulation, **verify the current Antigravity toolset** — if a native `AskUserQuestion` exists, prefer it and update this doc via `/skill-kit upgrade`. Do not treat the emulation steps below as authoritative until re-verified.

Track in-session work progress using the `task.md` artifact file.

## Role & Principle

- **Task Registration**: When user feedback or a decision is needed before registering, **ask first and only then register in `task.md`** — do not register immediately when the situation is ambiguous.
- **AskUserQuestion emulation**: The Antigravity (Gemini) agent has no `AskUserQuestion` tool. Emulate it by writing the question and options to `<appDataDir>/brain/<conversation-id>/ask.md` (`ArtifactType: "other"`, `RequestFeedback: true`).

## Storage

- **Path**: `<appDataDir>/brain/<conversation-id>/task.md`
- **Type**: Artifact (`ArtifactType: "task"`)

## Status Notation

| Notation | Meaning | Description |
|----------|---------|-------------|
| `- [ ]` | **Pending** | Not yet started |
| `- [/]` | **In Progress** | Currently working (only one at a time) |
| `- [x]` | **Completed** | Finished |

> **`[/]` scope**: `task.md` artifact only. Do NOT use `[/]` in plain markdown files (fix_plan.md, checklist.md, GitHub issue body, etc.) — express partial completion via the count of `[x]` sub-items.

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

## Called from resume.md

When invoked via `/wip` or "task cleanup + remaining work" (see [resume.md](./resume.md)), this topic provides the **Antigravity environment implementation** of resume's 3 steps:

| resume Step | Antigravity implementation |
|------------|----------------------------|
| Step 1: Cleanup (remove stale items) | Read `task.md` → identify lines to delete → remove them via `replace_file_content` |
| Step 2: Per-item direction ask | Emulate via `ask.md` (`ArtifactType: "other"`, `RequestFeedback: true`) — for each remaining item, offer proceed/split/merge/hold/delete options with Pros/Cons |
| Step 3: Start + execute | Use `replace_file_content` to flip the target line `[ ]` → `[/]` → do the work → `[x]` |

### Step 1 — task.md cleanup commands

```python
# Read task.md
existing = read_file("<appDataDir>/brain/<conv-id>/task.md")
# Targets: [x] completed entries (all or stale)
# Method: remove lines via replace_file_content (do NOT use write_to_file — it overwrites the whole file)
replace_file_content(
  path="<appDataDir>/brain/<conv-id>/task.md",
  old="- [x] Step 1 description\n- [x] Step 2 description\n",
  new=""
)
```

### Step 2 — ask.md per-item direction option format

Map resume Step 2's environment-agnostic labels (proceed / split / merge / hold / defer-to-checklist / delete) to ask.md options:

```markdown
# Remaining-item direction

### 1. [pending] #12 Add API endpoint
**Context**: New user lookup/update endpoint.

- [ ] A: Proceed — implement as currently defined
  - *Pros*: Fast progress along the existing definition
  - *Cons*: May affect downstream tasks
- [ ] B: Split — separate lookup vs update into distinct tasks
  - *Pros*: Isolates change impact
  - *Cons*: Two PRs to manage
- [ ] C: Defer to checklist — external wait, move to fix_plan.md hold section
  - *Pros*: Task list stays clean; item survives across sessions in the checklist medium
  - *Cons*: Needs an explicit trigger note for later re-promotion
- [ ] D: Delete — no longer needed
  - *Pros*: Less work
  - *Cons*: Risk of discovering it missing in a follow-up task

### 2. [pending] #13 Strengthen test coverage
...
```

Same format per item. 2–4 options per item (only the labels among the 6 that make sense for this task). "Defer to checklist" execution: append `- [ ] [BLOCKED] <subject> (trigger: ...)` to the checklist file, then remove the line from `task.md` (never keep both media).

## Workflow

### 1. Interactive Task Selection (Optional)

If there are multiple options, ambiguous instructions, or pending decisions (e.g., `[BLOCKED]` or `[NEEDS_REVIEW]` items), **DO NOT register them to `task.md` immediately**.
Instead, create `ask.md` via `write_to_file` (`ArtifactType: "other"`, `RequestFeedback: true`):

**CRITICAL RULES FOR `ask.md`**:
- **Include Context**: Briefly explain *what* the item is about so the user can make an informed decision without looking at other files (e.g., what the 3 fix items actually are).
- **Provide Trade-offs**: For every option (A, B, C), explicitly state the Pros and Cons (Trade-offs) so the user can weigh the choices.

```markdown
# Choose a direction

Select how to handle each of the following items (checkbox):

### 1. [REVIEW_FEEDBACK] PR #121 pending changes
**Context**: Three review items pending from the AI Review Summary (1. preserve `crud.ts` changes, 2. fix the autofocus bug, 3. add error handling).

- [ ] A: Implement now via code-workflow
  - *Pros*: Changes land quickly
  - *Cons*: Other urgent work gets delayed
- [ ] B: User edits manually
  - *Pros*: Fine-grained user control
  - *Cons*: Costs the user time and effort
- [ ] C: Skip
  - *Pros*: Focus on current work
  - *Cons*: Risk merging without addressing the feedback

### 2. Temp file cleanup
...
```

**CRITICAL CHAT PROMPT RULE**:
- **Use the Artifact UI**: When you create or update `ask.md`, you MUST set `ArtifactMetadata.RequestFeedback = true`. This triggers the system UI to automatically prompt the user.
- **Do NOT duplicate questions in the chat**: Because `ask.md` acts as the `AskUserQuestion` emulation, you must NOT list the questions, options, or unresolved items in your chat message. This creates redundant clutter.
- **Keep chat concise**: Your chat message should simply point to the artifact, e.g., "Please review the `ask.md` artifact on the right and leave your feedback."

### 2. Initialize

Once decisions are made (or if the task is clear from the start), create `task.md` via `write_to_file` with `ArtifactType: "task"`:

```markdown
- [ ] Step 1 description
- [ ] Step 2 description
- [ ] Step 3 description
```

### 3. Progress

Update task status using `replace_file_content`:

```markdown
- [x] Step 1 description
- [/] Step 2 description
- [ ] Step 3 description
```

### 4. Complete

Mark all items as `[x]` when done.

### 5. Add Items

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
