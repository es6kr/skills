# Research Topic (`research.md`)

## 1. Objectives

The research phase investigates technical feasibility, explores relevant code paths, and evaluates alternative architectures before finalizing an execution plan.

## 2. Research Deliverable Structure

When a task requires persistent research, author a dedicated research artifact named `research-<topic>.md` in `.agents/docs/generated/` using the canonical frontmatter schema:

```yaml
---
title: "Research: <Topic Title>"
created: YYYY-MM-DD
status: active
topic: <topic-slug>
language: en
relates_to:
  - "https://plane.es6.kr/es6kr/browse/<ID>"
---
```

## 3. Core Research Elements

1. **Problem Statement & Scope**: Clearly delineate what is being solved and what is out of scope.
2. **5-Why Root Cause Analysis**: When diagnosing bugs or regressions, trace the underlying failure mechanism down to architectural causes rather than stopping at surface symptoms.
3. **Current State Analysis**: Inspect existing code symbols, configuration files, and interfaces.
4. **Feasibility & Trade-offs**: Contrast at least two distinct approaches with empirical rationale.
