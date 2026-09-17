---
name: task-plan
metadata:
  author: es6kr
  version: "0.1.0"
description: General-purpose planning and research skill for software tasks. Integrates pre-search, deep research, layered roadmaps, comment cycles, proposals, and review gates. pre-search - RAG vector search and canonical medium gate [pre-search.md], research - deep codebase exploration and alternative analysis [research.md], plan - 3-tier deliverable hierarchy and 8 mandatory sections [plan.md], plan-guard - ambiguity detection and trade-off ask loop [plan-guard.md], proposal - business proposal and formal decision document [proposal.md], artifact-rules - volatile staging and canonical migration [artifact-rules.md], review - User Review Gate and worktree isolation [review.md]. "task-plan", "plan", "research", "proposal", "architecture plan", "planning" triggers
---

# Task Plan (`/task-plan`)

A comprehensive planning and research skill for engineering and organizational tasks.

## Topics

| Topic | Description | Guide |
|---|---|---|
| `pre-search` | RAG vector search, Qdrant memory lookup, and Canonical Medium Gate | [pre-search.md](./pre-search.md) |
| `research` | Deep codebase exploration, root-cause analysis, and alternative evaluation | [research.md](./research.md) |
| `plan` | 3-tier deliverable hierarchy (`roadmap-*.md`, `plan-*.md`) and 8 mandatory sections | [plan.md](./plan.md) |
| `plan-guard` | Ambiguity detection, comment cycles, and trade-off ask loop | [plan-guard.md](./plan-guard.md) |
| `proposal` | Business proposals, requisitions, and decision documents | [proposal.md](./proposal.md) |
| `artifact-rules` | Volatile brain session staging, metadata banners, and canonical migration | [artifact-rules.md](./artifact-rules.md) |
| `review` | Mandatory User Review Gate (`AskUserQuestion`) and worktree setup | [review.md](./review.md) |

## Quick Start

1. **Pre-search**: Run RAG and Qdrant memory queries to identify existing decisions.
2. **Research**: Explore the codebase, verify dependencies, and assess feasibility.
3. **Plan / Proposal**: Structure the deliverable using 3-tier naming and the 8 mandatory sections.
4. **Review Gate**: Present design and trade-offs to the user via interactive selection.
