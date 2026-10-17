# Hermes — native session task tracking

Hermes uses `todo_list` for WIP tracking and `clarify` for user decisions.
This topic takes precedence over Claude-specific API names in the shared workflow.
A missing `TaskList` or `TaskCreate` is normal in Hermes, not evidence that task tracking is unavailable.

## Discover and read first

1. Detect the Hermes runtime from the actual harness context, not a tool-name guess.
2. Use the exposed `todo_list`. If deferred, discover via `tool_search`, load its schema via `tool_describe`, then invoke via `tool_call`. Do not skip discovery just because the tool is not initially visible.
3. Call with no arguments and use the returned full list as the source of task IDs, contents, status and parent links:

```json
{}
```

Read before classifying registration/resume/mixed mode. Register before deliverable work, as required by the shared WIP entry procedure. Existing unrelated work must remain intact.

## Native operations

- **List:** no-argument `todo_list`.
- **Create/update:** set `merge:true` and explicit `id`, `content`, `status`; preserve `parent` when present. Choose a stable unique ID for a new task; update only IDs from a fresh list. No `subject`, `description`, `taskId` or Claude API payloads.
- **States:** `pending`, `in_progress`, `completed`, `cancelled`. One `in_progress` at a time. Do not reclassify or pause another active task merely to make room; resolve its actual state or ask via `clarify`.
- **Finish:** mark `completed` only after verifying the deliverable. Dispatch is not completion. Mark `cancelled` only for actual cancellation, not temporary blocking.
- **Delete:** `deleted` is not a valid status. Read the full list immediately before an authorized removal, preserve every unrelated task's `id`, `content`, `status` and optional `parent`, remove only authorized IDs, then submit the entire retained list with `merge:false`. Retain parents of surviving children or explicitly resolve those children first. Never use `merge:false` with only the currently selected task.
- **Verify:** use the full list returned by the write to read back changed IDs and preserved unrelated entries. If the tool fails or the result is uncertain, make a no-argument read before retrying; never blindly duplicate creates.

Example create/update payload (illustrative; use actual IDs and verified state):

```json
{
  "merge": true,
  "todos": [
    {"id": "wip-native-routing", "content": "Verify Hermes WIP native routing", "status": "pending"}
  ]
}
```

## Resume and decisions

Follow `resume.md`'s recovery and per-item direction workflow using the mappings above.
For Hermes, compaction alone does not make an `in_progress` task stale: re-read the native list and verify task evidence before changing its state. Do not delete or mark complete merely because it predates compaction.

Use native `clarify(questions=[...])`, not `AskUserQuestion` or `ask.md` emulation. Ask each independent item's direction separately (at most five questions per call). Respect the shared single-unambiguous-item exception; do not repeat approval for work already authorized. A choice authorizes only its stated scope.

## Fallback — only after actual unavailability

- Discover and attempt a harmless native list read first. Report the actual unavailability (missing tool after discovery or actual runtime failure), rather than treating the absence of Claude tools as a failure.
- Policy denial or an approval gate is not fallback permission. Do not route around it through a CLI, another ledger, or direct file writes. A transient timeout requires a fresh read/bounded retry, not an immediate change of task medium.
- Only use `agent-task` if an installed, verified adapter documents support for the actual Hermes current session ID and explicit per-session storage. Verify the adapter and its CLI schema first; this topic does not install it or invent flags. Require a verified current session ID from the runtime: no default/shared ledger, no guessed Discord channel ID, no old session ID from summaries.
- Do not copy tasks into a fallback ledger merely because it exists; avoid two active sources of truth. Preserve any native tasks and explain the selected medium and migration boundary.
- If the adapter or session ID cannot be verified, report the blocker and use `clarify` for a scoped checklist persistence decision. Do not silently drop tasks or claim native tracking succeeded.

## Verification

Run `python -m unittest discover -s skills/wip/tests -p test_hermes_contract.py -v` from the repository root.
These offline tests check the documentation contract, not LLM compliance or production execution. A safe runtime availability check is a no-argument `todo_list` read; do not fabricate task updates as evidence.
