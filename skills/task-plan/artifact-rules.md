# Artifact Rules Topic (`artifact-rules.md`)

## Deliverables Lifecycle & Staging Standards (HARD STOP)

1. **Volatile Brain Staging in Antigravity**:
   - Artifacts authored during active sessions (`plan-*.md`, `research-*.md`, `walkthrough-*.md`, `roadmap-*.md`) are initially staged in `brain/<conversation-id>/`.
   - Mandatory visible markdown review by the user prior to external repository publication.

2. **Canonical Destination Migration**:
   - Curated deliverables migrate to `.agents/docs/generated/` (or `llm-wiki/outputs/` via `raw-ingest`).
   - Automated detection & synchronization executed via `scan_unmigrated_artifacts.py`.

3. **Topic-Based Slug Naming Enforcement**:
   - Descriptive topic slugs required (`walkthrough-task-flow-engine.md`).
   - Generic date-only filenames (`walkthrough-2026-08-25.md`) strictly forbidden.
