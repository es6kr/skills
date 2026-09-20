---
name: task-flow
metadata:
  author: es6kr
  version: "0.1.0"
description: Universal task lifecycle orchestrator connecting research, planning, execution, and verification. pipeline - end-to-end task execution workflow [pipeline.md], compat-codeworkflow - backward-compatibility alias for code-workflow [compat-codeworkflow.md]. "task-flow", "flow", "lifecycle", "pipeline" triggers
---

# Task Flow (`/task-flow`)

Universal lifecycle orchestrator connecting research, planning, execution, and verification.

## Topics

| Topic | Description | Guide |
|---|---|---|
| `pipeline` | End-to-end task execution workflow connecting `task-plan` and `task-exec` | [pipeline.md](./pipeline.md) |
| `compat-codeworkflow` | Backward-compatibility wrapper for legacy `/code-workflow` | [compat-codeworkflow.md](./compat-codeworkflow.md) |

## Quick Start

1. Invoke `/task-flow` with your task or issue description.
2. **Prerequisite Gate (Stage 0)**: Check if prior brainstorming has been conducted. If not, invoke `superpowers:brainstorming` first and classify the request (Spike / Bounded / Architectural).
3. Follow Stage 1 (`task-plan`) to research prior decisions and structure the deliverable.
4. Pass through the mandatory User Review Gate (`AskUserQuestion`).
5. Follow Stage 2 (`task-exec`) to implement via TDD, verify empirical evidence, and deliver via PR.

