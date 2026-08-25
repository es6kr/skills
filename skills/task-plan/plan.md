# Plan Topic (`plan.md`)

## 3-Tier Deliverable Architecture (HARD STOP)

1. **Macro Roadmap (`roadmap-<epic-slug>.md`)**: Multi-repo/multi-runtime architectural evolution roadmaps with Mermaid flowcharts, coordinating 4+ independent plans.
2. **Hierarchical Parent Plan (`plan-<domain-slug>.md`)**: Domain-level overhaul coordinating multiple sub-tracks (T1, T2, T3) and inter-plan dependencies.
3. **Execution Sub-Plan (`plan-<task-slug>.md`)**: Concrete TDD implementation units containing the 8 mandatory sections.
4. **Walkthrough (`walkthrough-<topic-slug>.md`)**: Post-implementation verification logs using topic-based descriptive slugs (NEVER generic date names).

## Plane Issue Linking & Short Canonical Browse URL (HARD STOP)

When referencing Plane issues in Plan frontmatter (`relates_to`, `posted_to`), checklists, or commit logs:
- **Mandatory Canonical Browse URL**: MUST use the standard short Browse URL format: `https://<plane-host>/<workspace_slug>/browse/<PROJECT_ID>-<SEQUENCE_ID>` (e.g. `https://plane.es6.kr/es6kr/browse/ES6KR-123`).
- **Forbidden Anti-pattern**: Long internal UUID URLs (`/projects/<UUID>/issues/<UUID>`) are strictly prohibited.

## 8 Mandatory Plan Sections

1. **Approach & Architecture**: Clear high-level strategy and chosen design.
2. **Code Snippets**: Concrete code changes and signatures.
3. **Files to Modify / Create / Retire**: Explicit list of targeted paths.
4. **Trade-offs / Alternatives Table**: Pros, cons, cost, and rationale.
5. **Verification Plan Table**: `Target | Procedure | Command/URL | Expected Outcome`.
6. **Related Issue & Target Tracker**: Links to Plane issues and backlog items.
7. **Human Review Questions**: Purpose, behavioral diff, blast radius, ownership.
8. **Progress Checklist**: Granular per-phase checkboxes initialized to `[ ]`.

### Superpowers Integration
Delegates to `superpowers:writing-plans`.
