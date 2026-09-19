---
name: tdd
metadata:
  author: es6kr
  version: "0.1.0"
description: Test-Driven Development for coding and bug fixing. cycle - Red→Green→Refactor cycle, defining expected behavior, bug-fix TDD, anti-patterns, run - test execution workflow (environment detection→impact scope→execution→result reporting), test-strategies - boundary value·equivalence partitioning·decision table·error guessing·path coverage test design techniques. "TDD", "test first", "failing test", "doesn't work", "not working", "test design", "boundary value test", "test strategies", "equivalence partitioning", "bug fix", "run tests", "execute tests", "test run", "verify" triggers
---

# TDD (Test-Driven Development)

Test-Driven Development: define expected behavior first, then make it pass with implementation.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| cycle | Red→Green→Refactor cycle, bug-fix TDD, anti-patterns | [cycle.md](./cycle.md) |
| run | Test execution workflow (environment detection→impact scope→execution→result reporting) | [run.md](./run.md) |
| test-strategies | Boundary value·equivalence partitioning·decision table·error guessing·path coverage | [test-strategies.md](./test-strategies.md) |

## Quick Reference

### Trigger entry (HARD STOP — first action)

When this skill is invoked, the FIRST tool call must be TaskCreate (Red/Green/Refactor/Verify) + Red test authoring. Diagnosis, planning, option asks, and medium decisions are forbidden before Red is authored + executed + failure confirmed. See [cycle.md "Trigger entry"](./cycle.md).

### TDD Cycle
Define expected behavior → natural failure → implement → pass → refactor.
See [cycle.md](./cycle.md).

### Test Execution
Environment detection → impact scope → execution (unit→integration→e2e) → result reporting.
See [run.md](./run.md).

### Test Design Techniques
Decide which test cases to write (boundary value, equivalence partitioning, etc.).
See [test-strategies.md](./test-strategies.md).
