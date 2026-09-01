# Topic: create (Plane Issue & Intake Creation)

Handles physical creation of Plane Issues and Intake Issues via REST API with automatic K3s Django Shell fallback.

## Overview

When creating a Plane issue or registering a PlaneBacklog intake item, do not rely on manual browser clicks or unverified text placeholders. Use `plane_create_issue.py` to physically post the issue to the target workspace project.

## Execution Procedure

Resolve `BACKLOG_SCRIPTS` once per session:

```bash
for d in "${BACKLOG_SCRIPTS:-}" \
         "${CLAUDE_PLUGIN_ROOT:-}/skills/backlog/scripts" \
         "${AGENT_SKILLS_HOME:-$HOME/.agents}/skills/backlog/scripts" \
         "${GEMINI_SKILLS_HOME:-$HOME/.gemini/config}/skills/backlog/scripts"; do
  [ -n "$d" ] && [ -d "$d" ] && BACKLOG_SCRIPTS="$d" && break
done
```

### 1. Create Intake Issue (Default)

```bash
python3 "$BACKLOG_SCRIPTS/plane_create_issue.py" --title "[component] Issue title" --description "Detailed description text" --json
```

### 2. Create Regular Issue (Non-Intake)

```bash
python3 "$BACKLOG_SCRIPTS/plane_create_issue.py" --title "[component] Issue title" --description "Detailed description text" --no-intake --json
```

## Route Selection: Intake vs Regular Issue

**Intake is the default route.** A new backlog item lands in the triage inbox
(`POST .../intake-issues/`) so a human classifies and admits it before it reaches the active
tracker. Calling the plain issue endpoint for an untriaged item bypasses that admission step.

**Exception — P0 and P1 items register directly as regular issues (`--no-intake`).** Urgent and
high-priority work cannot absorb triage latency, and an item already classified P0/P1 has had its
priority decided, so routing it through the inbox adds a waiting step without adding a decision.
P2/P3 and unclassified items keep the intake default.

| Priority | Route | Flag |
|----------|-------|------|
| P0 (urgent) | Regular issue, direct | `--no-intake -p P0` |
| P1 (high) | Regular issue, direct | `--no-intake -p P1` |
| P2 (medium) | Intake (triage inbox) | *(default)* `-p P2` |
| P3 (low) | Intake (triage inbox) | *(default)* `-p P3` |
| Unclassified | Intake (triage inbox) | *(default)* |

| # | Don't | Do |
|---|-------|-----|
| 1 | Call the regular-issue route for an item whose priority has not been established | Unclassified means intake — the inbox is where the priority gets decided |
| 2 | Route a P0/P1 item through intake because "intake is the default" | The exception exists precisely because the triage step is already satisfied for these |
| 3 | Offer a creation option to the user without naming which route it takes | State the route and the priority in the option text — they determine whether a human triage step exists |
| 4 | Infer the route from how urgent the work feels | Read the priority off the source tracker entry, then apply the table |

**Self-check (before every `plane_create_issue.py` call)**: what priority does the source tracker
entry carry? P0/P1 takes `--no-intake`; everything else omits the flag. If the source carries no
priority, the route is intake.

## Resilience & Fallback Hierarchy

1. **Primary (REST API)**: Tries `x-api-key` using `PLANE_API_KEY` / `DGS_PLANE_API_KEY` or workspace profile token against `plane_host` REST API (`/api/v1/workspaces/<workspace>/projects/<project>/issues/`).
2. **Fallback (K3s Pod Shell)**: If REST API is unconfigured or returns HTTP 403, automatically falls back to `kubectl exec -n plane deploy/plane-api-wl -- python3 manage.py shell` to directly instantiate and save the `Issue` and `IntakeIssue` records in Django ORM.

## Output Schema

Returns structured JSON output:

```json
{
  "success": true,
  "method": "REST API" | "K3s Django Shell Fallback",
  "id": "86db2a42-172e-4413-98a2-9f5f704104e8",
  "sequence_id": 8,
  "title": "[es6kr/skills] Roll out PR 282, 283, 286 and live-verify",
  "url": "https://plane.es6.kr/es6kr/projects/4b4d8bfc-5e5d-495b-bd4c-301fe89e5bb0/issues/86db2a42-172e-4413-98a2-9f5f704104e8",
  "intake": true
}
```

After creation, attach the returned `url` to the tracker item: `→ Plane (<url>)`.
