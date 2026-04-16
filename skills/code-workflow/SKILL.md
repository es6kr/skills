---
name: code-workflow
metadata:
  author: es6kr
  version: "0.1.2"
depends-on: [github-flow, tdd, web-ui-test]
description: |
  4-stage workflow for code changes: research → plan → user review → implement (TDD). Applies to all tasks requiring code changes: issue implementation, fix_plan items, new feature additions. TDD (Red→Green→Refactor) is applied by default in the implementation stage; users can opt out with --no-tdd. After implementation, use github-flow/pr for PR creation and github-flow/plan-to-issue for issue registration.
  Use when: "coding workflow", "research plan implement", "research first", "write plan", "plan md", "user review", "review before implement", "code plan", "implementation process", "research md", "code changes".
---

# Coding Workflow

A **Research → Plan → User Review → Implement** 4-stage procedure for code change tasks.

Trivial tasks such as simple configuration changes or 1~2 line edits may skip this workflow.

## Topic Dependencies

```
code-workflow (steps 1-4)
  └─→ tdd/cycle (step 4: TDD implementation)
  └─→ tdd/run (step 4: test execution after implementation)
  └─→ github-flow/plan-to-issue (optional: register plan as issue)
  └─→ github-flow/pr (optional: create PR with visual attachments)
        └─→ web-ui-test (capture via Playwright)
```

- Steps 1-4 are always executed (unless trivial)
- `github-flow/plan-to-issue` (optional): converts plans to GitHub issues. Use when user requests issue registration
- `github-flow/pr` (optional): creates PRs after implementation. Use when user requests PR creation
- `tdd` is applied by default in step 4. Opt-out with `--no-tdd`

## Step-by-Step Procedure

### Step 1: Research (Read the Codebase)

Read and understand the relevant code **deeply**, then write findings to `.ralph/docs/generated/research-<task>.md`.

- Do not skim a file and move on at the signature level
- Understand existing layers, ORM relationships, and duplicate API presence
- **Mandatory exploration of existing test files**: Find related `*.test.*`, `*.spec.*` files and understand what cases are already covered
- Do not summarize in chat — **always write to a file**

### Step 2: Plan (Write Plan MD)

Write a detailed implementation plan in `.ralph/docs/generated/plan-<task>.md`.

Include:
- Detailed description of the approach
- Code snippets showing actual changes
- List of file paths to be modified
- Considerations / trade-offs
- **Verification plan** (required): For each change group, specify verification procedure, command/URL, and expected result

### Step 3: User Review

After writing the plan MD, report **STATUS: BLOCKED** and wait for user review.

Report content:
- Plan file path: `.ralph/docs/generated/plan-<task>.md`
- Number of changed files, summary of modification scope

Items for the user to verify:
- Is the approach appropriate?
- Is the modification scope within the issue/PR scope?
- Does it match existing patterns/conventions?

On user feedback → revise plan and re-review. On approval → proceed to step 4.

### Step 4: Implement (TDD applied by default)

Once the plan is approved, implement using the **tdd skill's cycle topic** (Red→Green→Refactor).
After implementation, run tests using the **tdd skill's run topic** and report results.

**TDD opt-out:** If the user specifies `--no-tdd`, implement without tests.

**Commit after implementation**: If build + tests pass, proceed to commit. Do not ask the user whether to commit. If a related existing commit exists, confirm whether to amend via `AskUserQuestion`.

Other:
- Mark completed tasks/steps as `[x]` in fix_plan.md
- Do not stop until all steps are complete
- Do not use `unknown` types
- Continuously run type checks during implementation (`pnpm typecheck` or `tsc --noEmit`)
- Do not introduce new type errors

## When Going in the Wrong Direction

Do not patch over a bad approach — revert and restart with a narrower scope.

```bash
cmd /c git checkout -- <files>   # revert changes
```

Revise the plan and restart from step 3 (user review).

## Applicability by Task Complexity

| Task Complexity | Scope |
|----------------|-------|
| trivial (1~2 line edits, config value changes) | Can be skipped — implement directly |
| moderate (3~10 files, logic changes) | Start from step 2 (plan) |
| complex (10+ files, new features, architecture changes) | Perform all steps from step 1 (research) |

## Self-Improvement

After this skill invocation completes, **self-improve based on the conversation**:

1. Detect limitations, failures, and workaround patterns for this skill in the conversation
2. If improvement candidates are found, run `/skill-kit upgrade code-workflow`
