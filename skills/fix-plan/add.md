# Add

New item authoring schema with Action / Why / How structure, length budget, and deliverable separation rules.

> **Scaffold placeholder** — Content migration from `ralph/fix-plan.md` (sections L46-86, L92-144) in progress. See plan `~/.agents/docs/generated/plan-fix-plan-migration.md` §4 for migration matrix.

## Planned Content

### Item format

```markdown
- [ ] {Action: imperative one-line}
  - **Why**: {motivation 1-2 sentences — what makes this required}
  - **How to apply**: {procedure / tools / commands}
  - {optional sub-steps or command examples}
```

### Three required elements

| Element | Purpose |
|---------|---------|
| Action | One-sentence verb-form description |
| Why | Information transfer to future sessions — context decays between sessions |
| How to apply | Concrete procedure (tools, commands, verification) |

### Length budget — verbose body forbidden

fix_plan item body = Action + Why + How (summary) + artifact path + external reference. Maximum ~5-7 lines.

Forbidden in fix_plan body:
- Full diagnostic results
- Reproduction evidence tables
- Fix-option matrix (A/B/C/D trade-off)
- Related-context lists (4+ items)
- Multi-step checklists (5+ items)

These belong in separate artifacts:

| Content kind | Artifact | Location |
|--------------|----------|----------|
| Diagnostic / reproduction / root-cause | `research-<slug>.md` | `docs/generated/` or `.ralph/docs/generated/` |
| Fix-option matrix / Test Plan / procedure | `plan-<slug>.md` | same |
| Multi-step (5+) checklist | `checklist-<slug>.md` | same |

fix_plan item references the artifact path as a one-line sub-bullet.

### Self-check before adding

1. Action: clear imperative verb-form?
2. Why: 1-2 sentences explaining context?
3. How: core procedure / tools / commands?
4. Future-session test: "Can a future session proceed without asking the user?"
