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
