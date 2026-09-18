# Doc Adapter Topic (`doc.md`)

## 1. Scope

When executing non-code tasks that produce documentation, architecture guides, executive summaries, or memos, the `doc` adapter provides standard structure and export capability.

---

## 2. Documentation Standards

1. **Language Compliance**:
   - Public open-source deliverables (`es6kr`, etc.): strictly English (`language: en`).
   - Internal deliverables: newly created docs in English for token conservation, or Korean when explicitly requested for internal stakeholders.
2. **Standard Headers**: Include canonical frontmatter (`title`, `created`, `status`, `topic`, `language`).
3. **Format Support**:
   - Technical walkthroughs: `.agents/docs/generated/walkthrough-*.md`
   - Executive memos and proposals: convert to `.docx` via `/docxport` when distribution to non-technical stakeholders is required.
