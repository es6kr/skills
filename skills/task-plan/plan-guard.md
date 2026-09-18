# Plan Guard Topic (`plan-guard.md`)

## 1. Overview

The Plan Guard prevents unvetted assumptions, ambiguous specifications, and unconfirmed trade-offs from slipping into execution.

---

## 2. Guard Rules & Checks

### 2.1 Ambiguity Detection
If a requirement is underspecified, ambiguous, or lacks clear acceptance criteria:
- Do NOT make speculative assumptions.
- Register an explicit entry under `## Human Review Questions`.
- Invoke `AskUserQuestion` / `ask_question` to resolve the ambiguity before writing production code.

### 2.2 Trade-off Validation Gate
Every non-trivial design decision must be evaluated in the Trade-offs Comparison Table. Proposing multiple alternatives in plain text without presenting structured interactive choices is strictly prohibited.

### 2.3 Deep Audit Delegation Handling
When authoring a plan intended for deep architectural audit (`audit_status: pending_*`):
- Do NOT force the user to make immediate low-level trade-off choices.
- Structure open questions as audit review points for the designated auditor.
