---
name: wip
description: |
  Track in-session work progress. Register steps for 3+ step tasks, update status per step, handle completion/abort.
  On /wip invocation, when remaining tasks exist, AskUserQuestion is required for the per-item direction (proceed / split / merge / hold / defer-to-checklist / delete) — asking only about start priority is forbidden.
  After a compact, show prior-work summary then AskUserQuestion(multiSelect) for restore selection and re-register via TodoWrite.
  antigravity - task.md artifact-based checklist (Antigravity environment) [antigravity.md],
  claude - TodoWrite/TaskCreate API guide (Claude Code environment) [claude.md],
  resume - environment-agnostic task cleanup + remaining-work workflow [resume.md].
  "wip", "track progress", "register tasks", "task register", "step tracking", "compact recovery", "task resume", "resume task", "cleanup + resume" triggers.
metadata:
  author: es6kr
  version: "0.1.1"
---

# WIP (Work In Progress)

Track current session work as a checklist.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| antigravity | task.md artifact-based checklist for Antigravity sessions | [antigravity.md](./antigravity.md) |
| claude | TodoWrite/TaskCreate API for Claude Code sessions | [claude.md](./claude.md) |
| resume | Environment-agnostic task cleanup + remaining-work workflow | [resume.md](./resume.md) |

## Topic Dependencies

```text
wip (entry — /wip or "task cleanup + remaining work")
  └─→ resume (environment-agnostic workflow)
        ├─→ claude (Claude Code: TaskList/TaskCreate/TaskUpdate/AskUserQuestion)
        └─→ antigravity (Antigravity: task.md artifact + ask.md emulation)
```

- **resume**: workflow procedure (cleanup → per-item direction ask → execute). Environment-agnostic.
- **claude / antigravity**: per-environment tooling. Defines how resume Step 1–3 is implemented in each environment.

## Purpose

Record in-progress work via **at least one** of:
1. **TodoWrite / TaskCreate** — in-session tracking
2. `checklist.md`, `fix_plan.md` and similar markdown files — persists across sessions
3. **Commit** — preserve incomplete code with a `WIP:` tag for later amend/squash

Emitting only a text summary without persistent recording does not satisfy `/wip`.

## When to Use

- Starting a multi-step task (3+ steps)
- User gives a large task instruction
- Need to show progress to the user
- When you want to record/preserve the current state mid-session
- "task cleanup + remaining work", "task cleanup", "remaining work", "resume" invocations

## /wip Entry Procedure (CRITICAL)

### Step 0 — args classification (HARD STOP, MANDATORY before Step 1)

**Before dispatching to any topic, classify the args intent.** The `/wip` skill has two mutually-exclusive dispatch paths — resume workflow vs new-task registration — and the wrong choice wastes user time and misapplies the resume gate.

Read args + call `TaskList` (Claude Code) or read `task.md` (Antigravity). Then classify:

| Signal | Mode | Dispatch |
|--------|------|----------|
| args contains **new-work instructions** (verbs like write / create / add / record / draft, referring to concrete deliverables), AND (existing tasks are 0 OR the new work is clearly independent) | **Registration mode** | Register new tasks via `TaskCreate` (Claude) / append lines to `task.md` (Antigravity). Skip resume workflow |
| args empty, or contains **cleanup/resume keywords** only (cleanup / remaining / resume / continue), AND existing tasks ≥1 | **Resume mode** | Follow 3 steps in [resume.md](./resume.md) |
| args contains **new-work instructions AND** existing tasks ≥1 with unclear direction | **Mixed mode** | (a) `TaskCreate` new work first, (b) then resume workflow on the combined list |
| args contains new-work instructions AND 0 existing tasks | **Registration mode** (0-task early exit) | `TaskCreate` only. Do NOT enter resume Step 1 (nothing to clean) |

**Self-check (before proceeding)** — answer all 5:

1. Did I read the args verbatim and identify verbs? (new-work verbs = registration; cleanup verbs = resume)
2. Did I call `TaskList` / read `task.md` to count existing tasks?
3. If 0 tasks and args has new-work verbs → am I about to call `TaskCreate` **directly**, not resume Step 1?
4. If mixed → am I calling `TaskCreate` first, then resume?
5. If I cannot classify with confidence → am I calling `AskUserQuestion` before dispatching?

### Step 1 — Resume workflow (only in Resume mode or Mixed mode's second phase)

**Follow the 3 steps in [resume.md](./resume.md)** in order:

1. **Cleanup**: immediately delete stale completed/in_progress entries (no user confirmation required)
2. **Per-item direction ask**: for each remaining item, decide proceed / split / merge / hold / defer-to-checklist / delete
3. **Start priority + execute**: among items decided as "proceed", choose start priority, mark in_progress, and execute

### Step 1 (alt) — Registration path (Registration mode)

1. Parse args into discrete work items (one per deliverable)
2. `TaskCreate` (Claude) or append lines to `task.md` (Antigravity) — one entry per item
3. If ≥2 items, `AskUserQuestion` for start priority; else mark the sole item `in_progress` and execute

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Enter resume Step 1 (Cleanup) blindly on every `/wip` invocation | Run Step 0 classification first. 0-task + new-work args = skip resume, go to Registration path |
| 2 | Interpret "3 steps in resume.md must follow" as unconditional | The 3-step chain applies only when Resume mode is selected (Step 0). Registration mode has its own 3-step path (parse → register → execute) |
| 3 | Force resume workflow onto args that request new deliverables | New-work verbs → Registration mode. Resume workflow does not apply to work that does not exist yet |
| 4 | Skip `TaskList` before deciding mode | `TaskList` is the primary source for existing-task count. Guessing from context memory is unreliable |
| 5 | Mixed mode: register new tasks + immediately mark in_progress without resume Step 2 direction ask on existing | Mixed mode: (a) register new, (b) then run resume on the combined list — old tasks may still need per-item direction |

Environment implementations:
- Claude Code → [claude.md](./claude.md) (TaskList/TaskCreate/AskUserQuestion)
- Antigravity → [antigravity.md](./antigravity.md) (task.md + ask.md)

**Prior violations**: see `~/.claude/skills/cleanup/data/failed-attempts.md` under keywords "wip resume dispatch", "wip cleanup skip", "wip registration vs resume".

## Quick Reference

### Resume (environment-agnostic)

`/wip` or "task cleanup + remaining work" → Step 1 cleanup → Step 2 per-item direction ask → Step 3 execute. Per-environment tooling lives in claude / antigravity.

See [detailed guide](./resume.md).

### Claude

Use `TodoWrite` for sequential steps, `TaskCreate` for parallel tasks with dependencies.
After compact, restore prior work: show summary → multiSelect → re-register via TodoWrite.

See [detailed guide](./claude.md).

### Antigravity

Use `task.md` artifact with standard markdown checkboxes (`- [ ]`, `- [/]`, `- [x]`).
Do NOT wrap checkboxes in backticks.

See [detailed guide](./antigravity.md).

## Skip Conditions

WIP tracking is unnecessary for:
- Single command execution (kubectl get, ls, etc.)
- Tasks with 2 or fewer steps
- Read-only queries
- User explicitly says "keep it simple"

## Rules (Sequential Flow)

- **One in_progress at a time** — applies to ordered/sequential tracking (TodoWrite/checklist mode)
- **Update immediately on completion** — mark completed as soon as done
- **No skipping** — proceed in order, don't start next step before completing current
