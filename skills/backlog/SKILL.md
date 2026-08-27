---
name: backlog
description: |
  Unified backlog lifecycle management and task tracking. Orchestrates session TODOs, workspace checklists (`fix_plan.md`, `checklist.md`), and issue trackers with vendor-agnostic lifecycle contracts.
  Topics — triage (classify incoming requests into session/file/issue backlogs), priority (GitHub-aligned P0-P3 urgency tagging and blocker triage), sync (external tracker status polling and resolution), prune (demote lower-priority backlog noise from active focus), lifecycle (authoring, state transitions, DoD criteria), comment (post follow-up notes/sub-findings to parent issues), create (issue and intake issue creation).
  Use when: "backlog", "backlog triage", "backlog sync", "backlog prune", "task lifecycle", "manage backlog", "backlog priority", "backlog cleanup", "plane backlog", "issue comment".
metadata:
  author: es6kr
  version: "0.1.0"
depends-on:
  - fix-plan
  - todowrite
  - github-flow
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Bash(gh:*)
  - Bash(python3:*)
---

# Backlog

Unified backlog lifecycle management and orchestration across multiple storage layers (session WIP, markdown checklist files, and issue trackers).

## Overview

The `backlog` skill provides a consistent operational interface for capturing, classifying, synchronizing, prioritizing, and maintaining backlogs across software development lifecycles.

```text
Incoming Task / Request
  ├─ In-Session Short-Lived  ──→ /wip (Session Task API / TodoWrite)
  ├─ Workspace Markdown File ──→ /fix-plan (fix_plan.md / checklist.md)
  └─ Team-Shared External    ──→ Issue Tracker (GitHub Issues / Forge / Secondary Trackers)
```

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| `triage` | Route incoming tasks to the appropriate persistence layer based on lifespan and collaboration scope | [triage.md](./triage.md) |
| `priority` | Apply P0–P3 priority tags (`[BLOCKED:P*:reason]`) and separate selfable vs external blockers | [priority.md](./priority.md) |
| `sync` | Poll remote and external forge states (`gh` CLI / Secondary Trackers) to reconcile completed tasks | [sync.md](./sync.md) |
| `prune` | Demote lower-priority items (P2/P3) and stale entries to preserve lean active focus sections | [prune.md](./prune.md) |
| `lifecycle` | Definition of Done (DoD), atomic marker transitions (`[ ]` → `[/]` → `[x]`), and archive rules | [lifecycle.md](./lifecycle.md) |
| `comment` | Post follow-up notes and nested review findings as comments on parent issues | [comment.md](./comment.md) |
| `create` | Create issues and intake items via API with fallback mechanisms | [create.md](./create.md) |

## Default Invocation (`/backlog`)

When invoked with no arguments, the `backlog` skill runs the standard health and synchronization pipeline:

1. **Sync**: Poll external status for linked issues and pull requests to update resolved items.
2. **Priority Triage**: Re-evaluate urgency and blockers across active items.
3. **Hygiene & Prune**: Identify bloated or stale tasks exceeding active capacity.
4. **Summary Report**: Output an actionable breakdown of immediate priority candidates.

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--file=<path>` | `fix_plan.md` | Target markdown checklist path for local operations |
| `--role=<pm\|deep\|impl>` | (unset) | Execution role profile filter for pipeline scoping |
| `--secondary-sync=<skill>:<topic>` | (unset) | Abstract receiver contract for non-GitHub backlog synchronization |

## Cross-Workspace & Secondary Trackers

Vendor-specific and proprietary tracker integrations (e.g. Jira, Plane, internal enterprise backlogs) are decoupled from this public core skill through abstract **Receiver Contracts** (`--secondary-sync`). Private multi-repo orchestrators handle proprietary endpoints without polluting public skill schemas.
