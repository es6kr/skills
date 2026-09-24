---
name: ralph
description: Guide and conventions for running the ralph autonomous loop tool (frankbria/ralph-claude-code) with Claude Code. Covers wrapper setup that avoids Circuit Breaker false positives, PUBLIC repo language guards for autonomous posting, and the workspace `.ralph/` artifact layout.
metadata:
  version: "0.1.0"
---

# ralph

Reusable knowledge for running `frankbria/ralph-claude-code` (an autonomous loop that drives `claude` to completion) against the Claude Code CLI. This skill is a **knowledge-only** reference — it ships no hooks and no agents. If you also want always-on enforcement (SessionStart guard injection, PreToolUse misuse blocking), you'll need to build that yourself for your own workspace; this skill only documents the patterns.

## When to use

- Setting up a new workspace for Ralph (`.ralphrc`, `claude-wrapper-ralph.sh`)
- Debugging Ralph Circuit Breaker (CB) OPEN states
- Authoring autonomous-loop prompts that may post to PUBLIC GitHub repos
- Understanding the `.ralph/` artifact layout (`fix_plan.md`, `docs/generated/`)

## When not to use

- For OMC's PRD-driven loop (a separate tool also named "ralph"), use that tool's own guide
- For one-shot tasks without persistence — Ralph adds overhead

## Wrapper setup (recommended for all Ralph workspaces)

Ralph's circuit breaker counts permission denials. Claude Code's permission system splits commands at `|`, `&&`, etc. without honoring shell quotes, so commands like `gh ... --jq '.[] | select(...)'` get denied even though they are safe. A wrapper that forces `--permission-mode bypassPermissions` works around this while your own destructive-command guard hooks (if any) stay active.

```bash
# ~/.ralphrc (per workspace)
CLAUDE_CODE_CMD="claude-wrapper-ralph.sh"
```

The wrapper script itself (e.g. at `~/.local/bin/claude-wrapper-ralph.sh`) and any PreToolUse destructive-command guard are outside this skill's scope — they are workspace/operator-specific enforcement, not generic knowledge.

## PUBLIC repo language guard (autonomous loops)

Ralph autonomous loops MUST translate non-English content to English before posting to any GitHub PUBLIC repo (issues, PRs, comments). A `--no-confirm` flag does not exempt this rule. Per-call procedure:

1. `gh repo view --json isPrivate -q '.isPrivate'` — `false` means PUBLIC
2. Scan the body for non-ASCII script characters; if any are found, translate to English first
3. Localized issue-drafts are pre-publish working files only — never `--body-file` them directly to a PUBLIC repo

## Artifact paths

| Path | Purpose |
|------|---------|
| `<workspace>/.ralphrc` | per-workspace Ralph config (`CLAUDE_CODE_CMD`, retries, `ALLOWED_TOOLS`) |
| `<workspace>/.ralph/fix_plan.md` | running task checklist (autonomous loop and supervisor share this file) |
| `<workspace>/.agents/docs/generated/plan-*.md` | per-task plan artifacts |
| `<workspace>/.agents/docs/generated/research-*.md` | per-task research artifacts |

"Workspace" here means the directory that contains `.ralph/` — typically a parent of one or more git repos, not the repo itself. Search for `.ralph/` at workspace level, not project level.

## Installation

```bash
clawhub install ralph
```

or add this marketplace and install the bundling plugin (this skill ships inside the `labs` plugin alongside other auxiliary skills):

```bash
claude plugin marketplace add https://github.com/es6kr/skills
claude plugin install labs@es6kr-skills
```

Either path provides this `SKILL.md` for reference only. It intentionally has no SessionStart guards and no PreToolUse hooks — those are enforcement concerns you add on top for your own workspace.
