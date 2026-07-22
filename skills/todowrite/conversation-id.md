# TaskList Conversation IDs (HARD STOP)

User-facing references to TaskList items must use the **subject prefix or subject keywords** — never the internal TaskList ID.

## Why

TaskList internal IDs (`#NNN`) collide visually with GitHub PR/issue numbers (also `#NNN`). When the assistant says "task #118", the user cannot tell whether this is PR #118, issue #118, or the TaskList row #118 — leading to constant guess-work.

## Scope of "conversation"

This rule applies to **every output the user can see or that downstream tools render**, not just plain assistant text:

| Medium | Self-check timing | Hookable? |
|--------|-------------------|-----------|
| **Response text (assistant output)** | Before generating every response. Most frequent violation site | No — cannot be blocked technically; the self-check is the only defense |
| `AskUserQuestion` option `label` / `description` | Right before each call | Yes — but only for sessions that START after the hook is registered. `block-tasklist-id-in-conversation.sh` (hook-kit/resources/, PreToolUse:AskUserQuestion) blocks bare `#NN`. **Long-running sessions load hooks at session start, so a session predating the hook's registration is NOT protected → the in-session self-check is the only defense there** (4th recurrence 2026-07-07: session started 06-29, hook re-homed 07-06) |
| `TodoWrite` content | Right before each call | No (no hook yet) |
| `TaskCreate` subject | Right before each call (subject already enforces a prefix → bare `#NNN` is forbidden) | Partially |
| `Edit` / `Write` description / arguments | Right before each call | No |
| Reports / tables in response | Right before writing | No |

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | "Completed task #104" | "Completed the Web-306 task" |
| 2 | "Cleaning up #328, #329" | "Cleaning up Fix-R4, Fix-C4" |
| 3 | `TaskCreate` subject with no prefix | Subject begins with `Web-PR-320:`, `IaC-18:`, `Fix-R1:`, etc. — prefix mandatory |
| 4 | `AskUserQuestion` option label `"#118 core clearStale (Recommended)"` | label `"core clearStale API task (Recommended)"` — reference by subject keyword |
| 5 | option description `"run #123 + #124 together"` | description `"run PR #123 consolidate + Copilot enrollment task together"` |

## Prefix format

`{project}-{issue}` or `{project}-PR-{pr#}`. Examples: `Web-306`, `IaC-18`, `Web-PR-320`, `Fix-R4`.

**If the subject already contains a `#NNN` PR/issue number, that becomes the conversational ID**:
- subject `#326 search-common — default value fix` → speak as `#326 search-common` or `search-common default value`
- subject `#326 user list — password verification` → speak as `#326 user list verification`

**Safe reference rule**: use `#NNN` only when the subject contains it as a PR/issue number. If the subject has no `#NNN`, reference by keyword (e.g., "core clearStale", "Ralph improve Step 5").

## Self-check (before every user-visible output — HARD STOP)

Common procedure for all media listed above:

1. Before writing, scan the body for `#<digit>` patterns — grep or visual inspection
2. If found, classify each: (a) PR/issue number, or (b) TaskList internal ID?
3. If (b) → **rewrite immediately** to subject prefix (Web-PR-NNN, IaC-NNN, Fix-RN, etc.) or subject keyword
4. When citing TaskList output (`#135 [pending] Web-PR-346`) in a response, render only the subject (`Web-PR-346 — verification on hold`)

### Forbidden patterns in response text (most frequent violation)

| # | Don't | Do |
|---|-------|-----|
| 1 | "**#135** Web-PR-346 verification" report | "**Web-PR-346** verification" — subject prefix only |
| 2 | "task #138 done" report | "Web-PR-352-info task done" — subject keyword |
| 3 | "4 fix-* items (#155, #156, #157, #158) cleaned" | "fix-0~3 4 items cleaned" — use the id prefix |
| 4 | Citing TaskList result (`#135 [pending] Web-PR-346`) verbatim in the response | Extract subject only when authoring response text |
| 5 | "ID" column of a report table showing #135, #136, #137 | Use the "Task" column with Web-PR-346, Web-PR-348, Web-PR-353 |

## Interpreting "remaining task N" references (HARD STOP)

When the user references a task by ordinal — "remaining task 1", "task #2", "next task" — interpret it against **the order shown in the status line (HUD)** visible to the user.

| # | Don't | Do |
|---|-------|-----|
| 1 | Interpret "remaining task 2" as the 2nd item among this session's fix-* tasks | The 2nd item in the pending list shown on the user's status line |
| 2 | Map by task ID order (#104, #108, ...) | Use the **display order on the status line** — that is what the user sees |
| 3 | Guess from your own context when ambiguous | Quote the status-line text directly and confirm. If still ambiguous, `AskUserQuestion` |

**Status line = primary source**: when the user's message includes status-line text (◼/◻ glyphs, task enumeration), that order **is** the user's numbering scheme.

## TaskList check obligation

Before starting new work, **always check TaskList first** — if pending tasks exist, handle them first or report to the user.

- After subagent completion, re-check TaskList before processing results
- Do not re-ask via `AskUserQuestion` for content already represented as a task — continue the existing task
- Do not ignore existing items and create new ones
- **Stale tasks from prior sessions**: if `TaskList` shows completed/in_progress tasks whose context is gone, run `TaskUpdate(status: "deleted")` to clear them — orphan tasks from prior sessions carry no usable context

## Reference

See `~/.claude/skills/cleanup/data/failed-attempts.md` "TaskList ID in conversation" entries for recurrence history.
