---
name: task-exec
metadata:
  author: es6kr
  version: "0.1.0"
description: Unified execution, implementation, and verification engine. Integrates TDD Red-Green-Refactor, code-discipline, multi-domain adapters, and completion verification. gate - plan acceptance gate [gate.md], implement - TDD execution [implement.md], code-discipline - quality and guard comments [code-discipline.md], doc - documentation adapter [doc.md], mail - briefing and email adapter [mail.md], verify - evidence verification [verify.md], delivery - branch finishing and PR publication [delivery.md]. "task-exec", "execute", "implement", "tdd", "delivery" triggers
---

# Task Exec (`/task-exec`)

Unified implementation, execution, and verification engine.

## Topics

| Topic | Description | Guide |
|---|---|---|
| `gate` | Plan acceptance prerequisite gate and worktree readiness check | [gate.md](./gate.md) |
| `implement` | TDD Red-Green-Refactor implementation engine | [implement.md](./implement.md) |
| `code-discipline` | Zero hallucination, minimal diffs, and GUARD comment discipline | [code-discipline.md](./code-discipline.md) |
| `doc` | Documentation adapter for technical guides and knowledge synthesis | [doc.md](./doc.md) |
| `mail` | Email, memo, and briefing dispatch adapter | [mail.md](./mail.md) |
| `verify` | Physical test execution and empirical evidence verification | [verify.md](./verify.md) |
| `delivery` | Branch finishing, commit-tidy staging, and PR publication | [delivery.md](./delivery.md) |

## Quick Start

1. **Gate Check**: Verify plan approval and active worktree state (`gate.md`).
2. **Execute Domain Adapter**: Run TDD for code (`implement.md`), or use doc/mail adapters for non-code deliverables.
3. **Verify**: Collect empirical test results and log verification evidence (`verify.md`).
4. **Deliver**: Stage logical units via `commit-tidy` and open/merge PR (`delivery.md`).
