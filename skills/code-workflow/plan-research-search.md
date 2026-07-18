# Plan/Research Pre-Search Obligation (HARD STOP)

Mandatory plan/research pre-search on entering a Task/issue/PR. Applies equally to **query/verification** entry actions, not only changes.

## Rule Body

When the user mentions `#N` or a domain keyword, the first action is a **Glob search for plan/research files**. **Plan Glob comes before** query commands such as `gh issue view`, `gh pr view`, and `git log`. When found, **Read the body and map it to the work scope** → add a cross-reference to tracking documents such as fix_plan.md.

### Trigger Verbs (all apply equally)

Both change verbs and query verbs trigger this rule:

- Change/action: "handle", "implement", "fix", "correct", "Resume", "restart", "start"
- **Query/verification**: "check progress", "status check", "how far along", "how is it going", "status", "current state", "query", "confirm"
- Analysis/planning: "analyze", "review", "plan", "next task"

### Trigger Keywords (domain)

Domain keywords in task descriptions and user messages are equal triggers alongside `#N`:

- Filenames/paths: specific files such as `deploy-master.yml`, `inventory.yml`, `proxy.ts`, `examples.tf`
- Tool/service names: `blueprint`, `semaphore`, `terraform`, `authentik`, `argocd`, etc.
- Job/step/resource names: workflow job names, terraform resources, ansible roles, etc.
- Work code names: task-unit aliases such as `Web-E2E-A/B/C`, `SSO-FIX-1`

Run all of the above items as **separate queries** (no single-prefix matching; multi-keyword OR matching instead).

## Don't / Do Table

| # | Don't | Do |
|---|-------|----|
| 1 | Proceed based only on TaskGet description | Run `Glob('**/.ralph/docs/generated/*<issue-number>*.md')` first → Read the plan if found |
| 2 | Assume "task description has enough information" | Task description is a summary; the plan contains the higher-level design. Check both before starting work |
| 3 | Complete only part of the plan and mark the task as completed | Create a mapping table between all plan items (§3, §4, etc.) and work results → split unfinished items into separate tasks |
| 4 | Omit the plan file reference when updating fix_plan.md after completing work | Explicitly state "Related plan: `.ralph/docs/generated/plan-<N>-<slug>.md`" and include a completed/unfinished items table |
| 5 | Assume a simple query like "check issue progress" does not require a plan search | A query is also an entry action. Run plan Glob before calling `gh issue view <N>`. When a plan is found, evaluate progress from the plan body (do not judge from code grep alone) |
| 6 | Assert "0% progress" based only on `gh issue view` + `git branch \| grep <N>` + code grep | When a plan exists, build a done/not-done matrix by plan §N units. Use direct grep results as primary sources only after confirming the plan is absent |
| 7 | Force only the `plan-*` prefix in Glob (e.g., `find -name 'plan-*blueprint*'`) — missing other format files (research-, analysis-, `<topic>-drift.md`, `<topic>.md`) | Search using keyword matching regardless of prefix: `find -iname '*<keyword>*.md'` or `Glob('**/.ralph/docs/generated/*<keyword>*')`. Use keyword-only matching to include all formats such as `plan-/research-/analysis-/...-drift.md` |
| 8 | Skip Read for any Glob/find result by guessing "probably not directly related to this task" | **Mandatory Read for every found file**. No guessing. Determine irrelevance only after reading the body |
| 9 | Search only one keyword from the task description (filename/tool name) and assert plan absence on 0 results | **Exhaustively extract** all domain keywords from the task description and run a separate Glob for each. Also search code names from user messages (e.g., `Web-E2E-B`) as separate keywords |

## Self-Check (every time on task entry — including query actions)

1. Does the user message contain an issue/PR number (`#N`) or a domain keyword? — **Search is mandatory regardless of change intent**
2. Have **all domain keywords** been extracted from the task description? (filenames, tool names, work code names — all of them)
3. Was `Glob '**/.ralph/docs/generated/*<keyword>*'` run per keyword before calling `gh issue view` / `gh pr view` / `git log`? (no single-prefix assumption)
4. Did the Glob/find command match on `*<keyword>*` alone without forcing a prefix like `plan-*`?
5. Were all found files Read? — No skip-by-guess if even one file was found
6. Was plan absence explicitly confirmed? (empty results for all keywords = may be cited as primary source)
7. Were unfinished items identified? Were they registered as separate tasks or in the fix_plan.md BLOCKED section?
