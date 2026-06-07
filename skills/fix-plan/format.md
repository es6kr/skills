# Format

Schema and structure for fix_plan.md / checklist.md files.

> **Scaffold placeholder** — Content migration from `ralph/fix-plan.md` in progress. See plan `~/.agents/docs/generated/plan-fix-plan-migration.md` §4 for migration matrix.

## Planned Content

- Top-level structure: `## Progress` and `## Completed` sections
- Marker syntax: `- [ ]` pending, `- [x]` completed (pending move), `- [BLOCKED]` skipped
- Item state changes: session ID + timestamp annotation on completion
- Section-consistency check (item state must match section meaning)
- Default execution flow when topic invoked
- Forbidden actions (do not empty Progress, do not modify Completed retroactively)
