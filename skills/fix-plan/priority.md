# Priority — BLOCKED P0-P3 + Reason Classification

GitHub priority label-aligned BLOCKED suffix syntax + reason classification to surface self-progressable items that are currently buried under blanket `[BLOCKED]` tags.

> **Scaffold placeholder** — Full convention authoring in progress. See plan `~/.agents/docs/generated/plan-fix-plan-migration.md` §5 for the complete specification.

## Planned Content

### Syntax

```markdown
- [BLOCKED:P0]                            # Priority only
- [BLOCKED:P0:external]                   # Priority + reason
- [BLOCKED:P1:selfable] {Action}          # Self-progressable, P-rank for immediate action
```

### Priority scale (GitHub-aligned)

| Priority | Meaning | GitHub label analog |
|----------|---------|---------------------|
| P0 | Highest — blocks all other work | `priority:0`, `critical` |
| P1 | High — should resolve this session/cycle | `priority:1` |
| P2 | Medium — next session OK | `priority:2` |
| P3 | Low — optional / nice-to-have | `priority:3` |

### Reason classification

| Reason | Meaning | Action |
|--------|---------|--------|
| `external` | True external dependency (user / bot / CI / teammate) | Cannot proceed without external response |
| `selfable` | Progressable now (branch + body ready, refactor available, pure code work) | Process in next P-ranked work — NOT actually blocked |

### Triage workflow

1. Scan all `[BLOCKED]` entries
2. Extract `:P*` + `:reason` (propose adding if missing)
3. Sort: P0 selfable → P0 external → P1 selfable → P1 external → P2 → P3
4. Report top-3 candidates for immediate action (P0 + P1 selfable)

### Self-check on tagging `[BLOCKED]`

1. Truly blocked, or `:selfable`? — selfable items get P-ranked into immediate work instead
2. Priority axis: blocker-for-others (P0), session blocker (P1), next-session (P2), nice-to-have (P3)?
3. Reason annotation matches (external if waiting on user/bot/CI; selfable if just deferred)?
