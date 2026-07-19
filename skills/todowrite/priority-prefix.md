# Priority Prefix

Encode task **priority** and **execution order** in the TaskList subject line when the Task tool exposes no native priority field. `TaskCreate` / `TaskUpdate` offer only `subject`, `metadata`, and `addBlockedBy` / `addBlocks` — there is no `priority` argument. This topic standardizes a subject-prefix convention so priority is visible at a glance and order is enforced by dependencies.

## Why

- `TaskList` sorts by **ID**, not priority. With many tasks, ID order ≠ importance order.
- `metadata.priority` is stored but **not surfaced** in `TaskList` output — invisible when scanning.
- A subject prefix is the only priority signal visible in every `TaskList` row.

## Prefix format

`P{priority}-{Project}-{Phase|desc}`

- `{priority}` — integer tier, `P0` highest (`P0` critical → `P3` deferred).
- `{Project}` — short project/area name (e.g. `Auth`, `Guards`).
- `{Phase|desc}` — phase number or short descriptor.

Example: `P0-Auth-Phase-2`

### PR / issue anchor

When a task tracks an in-progress or in-review PR/issue, anchor the prefix on that number instead of a generic project name:

- `P{n}-PR{num}-{desc}` — e.g. `P1-PR128-consolidate`
- `P{n}-issue{num}-{desc}` — e.g. `P2-issue90-verify-adjudication`

The number then stays visible in every TaskList row, so you never re-look-up which PR/issue a task belongs to.

## Exception — active skill-workflow tasks

Tasks that belong to an **active, ordered skill workflow** (e.g. the `fix` skill's fix-1 → fix-4 steps) use a **workflow-order prefix** instead of `P{n}`:

- `fix-1`, `fix-2`, … — sequence within the workflow
- `{skill}-{N}` — for other numbered workflows

### Ranking

Workflow tasks outrank priority tiers. Full order (top first):

```
fix-*  (active workflow)  >  P0  >  P1  >  P2  >  P3
```

An active workflow is the current focused work — it sorts above any `P0` because it must finish (or be explicitly paused) before switching to a priority-tier task.

## Execution order via dependencies

Priority tier is **importance**, not a schedule. To enforce *execution* order, use dependencies — orthogonal to the prefix tier:

- `TaskUpdate(taskId, addBlockedBy: ["<id>"])` — this task cannot start until `<id>` completes
- `TaskUpdate(taskId, addBlocks: ["<id>"])` — inverse

Example: verification tasks gated behind a rollout task — `P2-PR70-verify-…` `addBlockedBy` `P1-PR70-rollout-…`. The verify tasks stay unclaimable until rollout completes, regardless of their `P2` tier.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Answer "TaskUpdate has no priority field" and stop with prose ("let me know if you want me to organize") | Apply this prefix convention to the existing tasks immediately — renaming subjects is cheap and reversible |
| 2 | Leave many tasks in ID order when the user asks about priority | Assign P-tiers + set dependencies, then report the sorted view |
| 3 | Use `P{n}` for active skill-workflow steps | Use `fix-1`..`fix-N` (workflow-order); they outrank `P0` |
| 4 | Encode execution order only in the prefix number | Prefix = importance tier; use `addBlockedBy` / `addBlocks` for execution gating |
| 5 | Invent priority tiers silently and treat them as final | Priority is the user's axis — propose tiers, note they are adjustable (subject rename), let the user veto |

## Self-check (when the user has many tasks or asks about priority)

1. Does `TaskList` show 4+ tasks in plain ID order? → apply the prefix convention
2. Does any task track a PR/issue in flight? → anchor its prefix on that number
3. Are any tasks part of an active skill workflow? → use `fix-N` / `{skill}-N`, rank above `P0`
4. Is there a real execution dependency (A must finish before B)? → set `addBlockedBy`, don't rely on the tier number
5. Did you propose the P-tiers as adjustable rather than final?
