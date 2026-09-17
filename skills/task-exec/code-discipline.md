# Code Discipline Topic (`code-discipline.md`)

## 1. Principles of Code Discipline

1. **Minimal Atomic Changes**: Only modify lines directly related to the current unit task. Avoid cosmetic reformattings or unrelated refactorings.
2. **Zero Hallucination**: Every imported package, function call, and CLI flag must be physically verified against existing codebase conventions or official documentation.
3. **Preserve Integrity**: Do not remove existing docstrings, license headers, or Byte Order Marks (BOM). Do not introduce trailing empty lines.

---

## 2. GUARD Comment Protocol

When writing structural defensive checks, validation filters, or exception handlers:
- Prepend a concise inline technical comment explaining *why* the check exists and *what* failure mode it prevents (e.g. referencing an issue, recurrence count, or edge case).
- Ensure comments describe invariants rather than obvious line-by-line syntax.
