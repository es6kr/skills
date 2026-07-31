---
name: plane-backlog
description: |
  Integrated lifecycle backlog and schedule management for Plane, LLM Wiki, Qdrant, and Markdown Checklists.
  Supports multi-workspace isolation (es6kr vs daegunsoftDev), pre-creation context lookup (`/plane-backlog pre-lookup <topic>`),
  post-creation automatic indexing (`/plane-backlog post-ingest <path>`), and Plane API status sync (`/plane-backlog sync`).
  Use when: "plane backlog", "plane sync", "backlog lifecycle", "pre-lookup", "post-ingest", "llm-wiki sync".
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

Integrated backlog, schedule, LLM Wiki, and Qdrant semantic search lifecycle management for multi-workspace development environments (`es6kr` & `daegunsoftDev`).

## Quick Commands

Resolve the `fix-plan` scripts directory once per session — the same scripts ship in both agent runtimes (Claude Code: `~/.agents/...`, Antigravity/Gemini: `~/.gemini/config/...`):

```bash
for d in ~/.agents/skills/fix-plan/scripts ~/.gemini/config/skills/fix-plan/scripts; do
  [ -d "$d" ] && FIX_PLAN_SCRIPTS="$d" && break
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

## Lifecycle Flow

```text
[Pre-Lookup] -> [Artifact Creation] -> [Wiki Page Compilation (pages/*.md)] -> [Post-Ingest to Qdrant] -> [Checklist & Plane Sync] -> [Wiki Refinement]
```

## LLM Wiki Storage Architecture (HARD STOP)

- **Authoritative plans under `pages/`**: plan and architecture documents live under `pages/<domain>/<name>.md` (e.g. `pages/workflow/<name>.md`) as single authoritative documents. Do not dual-store plan content under `raw/`, and do not keep a duplicate copy of an authoritative plan in `outputs/` — archive superseded duplicates instead.
- **Session artifacts under `outputs/`**: research and walkthrough artifacts produced by working sessions live under `outputs/` and are registered in `index.md`. Promote a session artifact to `pages/` only when it becomes authoritative knowledge.
- **Raw Limit**: Restrict `raw/` exclusively to raw uncurated external inputs (PDF text extractions, external manuals). Creating `raw/` files for plans is strictly prohibited.
- **Leftover Cleanup**: Once plan/knowledge is compiled under `pages/`, purge all residual drafts or duplicate copies in `raw/` or scratch directories using `git rm` or `safe-delete`.
- **Workspace Contamination Guard**: Cross-verify workspace boundaries before saving wiki files (`pages/`). Prevent cross-repository pollution between `es6kr` and `daegunsoftDev`.
- **Index & Ingest Execution**: After creating a `pages/` file, update `index.md` and `log.md`, commit changes, and run `artifact_post_ingest.py` for Qdrant ingestion.
