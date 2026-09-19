# Plan Topic (`plan.md`)

## 1. 3-Tier Deliverable Hierarchy

Complex engineering projects must avoid monolithic flat plans. Use the 3-tier deliverable hierarchy:

1. **Tier 1: Macro Roadmap (`roadmap-<topic>.md`)**: Long-term vision, strategic milestones, cross-repository scope, and architectural epochs.
2. **Tier 2: Parent Architecture Plan (`plan-<topic>.md`)**: Concrete system design, subsystem interfaces, and cross-cutting trade-offs for an entire milestone or feature set.
3. **Tier 3: Sub-Plan (`plan-<topic>-<subtopic>.md`)**: Atomic, independently verifiable implementation plans focused on a specific component, adapter, or workflow.

---

## 2. Mandatory Plan Sections (HARD STOP)

Every plan artifact MUST contain the following 8 core sections:

1. **YAML Frontmatter**:
   ```yaml
   ---
   title: "Plan: <Title>"
   created: YYYY-MM-DD
   status: draft
   topic: <topic-slug>
   language: en
   relates_to:
     - "https://plane.es6.kr/es6kr/browse/ES6KR-123"
   ---
   ```
   - Must contain `created: YYYY-MM-DD` (never replace with bare `date:`).
   - Links must use canonical standard browse URLs (`https://<host>/<slug>/browse/<ID>`), never internal API paths with UUIDs.
2. **Executive Summary & Scope**: Clear description of problem and scope boundary.
3. **Architecture Diagram**: Mermaid flowchart illustrating deliverables and component flow.
4. **Detailed Specifications**: File-by-file changes, schemas, and behavior.
5. **Trade-offs Comparison Table (MANDATORY)**: Comprehensive comparison contrasting the selected approach against alternatives.
6. **Human Review Questions (MANDATORY)**: Explicit open decisions or confirmation items for the user.
7. **Progress Checklist (MANDATORY)**: Unit task breakdown with single-responsibility items.
8. **Verification Plan (MANDATORY)**: Structured table format:
   ```markdown
   | Target | Procedure | Command / URL | Expected Outcome |
   |---|---|---|---|
   ```
