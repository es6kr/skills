---
name: plane-backlog
description: |
  Integrated lifecycle backlog and schedule management for Plane, LLM Wiki, Qdrant, and Markdown Checklists.
  Supports multi-workspace isolation (e.g. a public skills workspace vs a private company workspace), pre-creation context lookup (`/plane-backlog pre-lookup <topic>`),
  post-creation automatic indexing (`/plane-backlog post-ingest <path>`), and Plane API status sync (`/plane-backlog sync`).
  Use when: "plane backlog", "plane sync", "backlog lifecycle", "pre-lookup", "post-ingest", "llm-wiki sync", "plane comment", "issue comment", "backlog canonicalization".
metadata:
  author: es6kr
  version: "0.1.0"
depends-on:
  - fix-plan
  - es6kr
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Bash(python3:*)
  - Bash(uvx:*)
---

# Plane Backlog Integration Skill

Integrated backlog, schedule, LLM Wiki, and Qdrant semantic search lifecycle management for multi-workspace development environments (e.g. `es6kr` and other private workspaces).

## Quick Commands

Resolve the `fix-plan` scripts directory once per session. `fix-plan` ships in this same plugin, so the plugin root resolves it in any runtime; the remaining candidates cover standalone skill installs and stay overridable per environment:

```bash
for d in "${FIX_PLAN_SCRIPTS:-}" \
         "${CLAUDE_PLUGIN_ROOT:-}/skills/fix-plan/scripts" \
         "${AGENT_SKILLS_HOME:-$HOME/.agents}/skills/fix-plan/scripts" \
         "${GEMINI_SKILLS_HOME:-$HOME/.gemini/config}/skills/fix-plan/scripts"; do
  [ -n "$d" ] && [ -d "$d" ] && FIX_PLAN_SCRIPTS="$d" && break
done
```

### 1. Pre-Creation Lookup (Before creating Plan or Research)
```bash
python3 "$FIX_PLAN_SCRIPTS/artifact_pre_lookup.py" "<topic or title>"
```

### 2. Post-Creation Ingest (After creating Plan or Research)
```bash
python3 "$FIX_PLAN_SCRIPTS/artifact_post_ingest.py" <path/to/artifact.md>
```

### 3. Plane Checklist Sync
```bash
python3 "$FIX_PLAN_SCRIPTS/plane_sync.py" --dry-run
```

### 4. Workspace Profile Verification
```bash
python3 "$FIX_PLAN_SCRIPTS/workspace_profile.py" --json
```

### 5. Plane Issue & Intake Creation
```bash
python3 "$FIX_PLAN_SCRIPTS/plane_create_issue.py" --title "<title>" --description "<description>" --json
```

### 6. Plane Issue Comment Creation
```bash
python3 "$FIX_PLAN_SCRIPTS/plane_create_comment.py" --issue "<issue_uuid>" --comment "<text>" --json
```

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| comment | Post a comment onto an existing Plane Issue (escaped HTML + Cloudflare UA + 429 backoff); used to attach a parent item's nested sub-findings | [comment.md](./topics/comment.md) |
| create | Physical creation of Plane Issues / Intake Issues via REST API with K3s Django Shell fallback | [create.md](./topics/create.md) |

## Lifecycle Flow

```text
[Pre-Lookup] -> [Artifact Creation] -> [Wiki Page Compilation (pages/*.md)] -> [Post-Ingest to Qdrant] -> [Checklist & Plane Sync] -> [Wiki Refinement]
```

## Known Gotchas

### Issue `description` vs `description_html` — the API PATCH does not populate the editor's field

Plane's Issue model has (at least) three description-related fields:

- `description` — a TipTap/ProseMirror JSON document. **This is the field the web rich-text editor actually reads when a user opens an issue.**
- `description_html` — a cached HTML string used for list/detail read-only previews.
- `description_stripped` — plain-text derivative (search indexing).

`PATCH /issues/<id>/` (or Django `Issue.save()`) accepting `description_html` does **not** auto-derive `description`. If you bulk-write only `description_html` (e.g. wrapping raw markdown in `<pre>` as a quick migration shortcut), the result is: (1) the read-only preview shows literal markdown syntax instead of rendered text, and (2) opening the issue in the editor shows **blank content**, because `description` is still `{}`.

**Fix**: convert markdown to real HTML (`<strong>`, `<ul><li>`, `<code>`, etc. — not `<pre>`-escaped raw text) before writing `description_html`. If the editor-blank problem also needs fixing, `description` (the JSON doc) must be populated separately — the REST API does not do this for you.

## LLM Wiki Storage Architecture (HARD STOP)

- **Authoritative plans under `pages/`**: plan and architecture documents live under `pages/<domain>/<name>.md` (e.g. `pages/workflow/<name>.md`) as single authoritative documents. Do not dual-store plan content under `raw/`, and do not keep a duplicate copy of an authoritative plan in `outputs/` — archive superseded duplicates instead.
- **Session artifacts under `outputs/`**: research and walkthrough artifacts produced by working sessions live under `outputs/` and are registered in `index.md`. Promote a session artifact to `pages/` only when it becomes authoritative knowledge.
- **Raw Limit**: Restrict `raw/` exclusively to raw uncurated external inputs (PDF text extractions, external manuals). Creating `raw/` files for plans is strictly prohibited.
- **Leftover Cleanup**: Once plan/knowledge is compiled under `pages/`, purge all residual drafts or duplicate copies in `raw/` or scratch directories using `git rm` or `safe-delete`.
- **Workspace Contamination Guard**: Cross-verify workspace boundaries before saving wiki files (`pages/`). Prevent cross-repository pollution between the public skills workspace and any private company workspace.
- **Index & Ingest Execution**: After creating a `pages/` file, update `index.md` and `log.md`, commit changes, and run `artifact_post_ingest.py` for Qdrant ingestion.
