# Guardrails

Cross-cutting checks applied before any action the agent takes during a pipeline run. Self-contained — the harness ships a conservative default set so it can guard execution in headless runtimes where richer guard machinery (hooks, ask-user plugins) may be absent.

```text
denylist            → block destructive operations without explicit user authorization
scope check         → bound work to the user's stated request; refuse drift
conditional reject  → on ambiguous instructions, ask instead of guessing
```

## When to Use

- Wrapping an autonomous agent that runs without a human-in-the-loop on each step
- Replaying a workflow that previously executed destructive operations or drifted out of scope
- Establishing a minimum guard floor before plugging in richer guard machinery via `--guard=<skill>:<topic>`

## Self-contained defaults

The harness owns these defaults so it can operate detached from the larger skill set. Receivers like `hook-kit` and `ask-user` add capability when present, but they are not required.

### Default denylist (destructive operations)

| Class | Examples | Default behavior |
|-------|----------|------------------|
| Filesystem | `rm -rf`, `rm -f /`, `find … -delete` (broad) | Block — require explicit user authorization with the exact path |
| Git | `git push --force`, `git reset --hard`, `git checkout -- .`, `git clean -f`, `git branch -D` | Block — require explicit user authorization |
| Database / state | `DROP TABLE`, `TRUNCATE`, `rm -rf <data-dir>` | Block — require explicit user authorization |
| Process | `kill -9 <pid>` against unknown processes | Block — require explicit user authorization |
| Hooks bypass | `--no-verify`, `--no-gpg-sign`, `--force` against `main`/`master` | Block — require explicit user authorization |

The user authorizes by naming the exact operation (not "yes" to a generic prompt). Authorization is single-use; the same operation against a different path requires re-authorization.

### Scope check

Work scope is anchored to the user request text. The check reads two inputs:

- **scope source** — the user's request (default) or a custom origin via `--scope-source=<path>`
- **observed effect** — the set of files / commands / API calls the agent is about to perform

The guardrail blocks any observed effect outside the scope source's natural surface, unless the user authorizes the broader effect.

| # | Don't | Do |
|---|-------|-----|
| 1 | Refactor adjacent code while fixing the requested bug | Touch only the code the request targets; flag adjacent issues as separate findings |
| 2 | Delete pre-existing dead code "while you're here" | Removing pre-existing code requires explicit user authorization |
| 3 | Bundle unrelated improvements ("better naming") into a scoped change | Improvements outside scope are separate suggestions, not silent commits |

### Conditional reject

When the user's instruction is ambiguous, the guardrail rejects the silent-proceed path and forces a clarifying question. Triggers:

- Multiple plausible interpretations of a verb / subject
- Missing referent ("fix it" with no clear `it`)
- Conflicting constraints in the request ("keep it simple but also add caching")
- Destructive operation against an unconfirmed target

The harness raises a clarifying question via the runtime's question mechanism (the runtime decides how — the harness does not embed a specific ask mechanism).

## Dispatch — richer guard machinery

When the environment offers richer guard machinery (a hook framework, an interactive ask mechanism, a policy engine), plug it in via the abstract `--guard=<skill>:<topic>` flag.

```bash
# Use built-in defaults only
/harness pipeline "Refactor auth"

# Plug in richer guards (e.g., a hook-based pre-execution gate)
/harness pipeline "Refactor auth" --guard=my-org-policy:enforce
```

The receiver, when present, is consulted in addition to the built-in defaults. The receiver may extend the denylist, refine the scope check, or override the conditional-reject behavior — but it cannot weaken the built-in floor.

## Composition with pipeline stages

Guardrails are checked at the entry of stages 3, 4, and 5 of the pipeline:

| Stage | Guardrail purpose |
|-------|------------------|
| Plan (stage 3) | Block plans that include denylisted operations; flag scope drift in proposed file targets |
| Generate (stage 4) | Block destructive operations during execution; flag observed effect outside scope |
| Verify (stage 5) | Confirm that the diff matches the plan's file targets (post-hoc scope check) |

Stages 1 and 2 (clarify, ground) are read-only by design and do not need guard checks.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat a successful test run as proof that the change was in scope | Run the scope check separately; tests can pass on out-of-scope changes |
| 2 | Use a generic "are you sure?" prompt for destructive authorization | Quote the exact command and target; authorization is per-operation, not generic |
| 3 | Disable the built-in floor because a custom receiver was supplied | The receiver layers on top of the floor; lowering the floor needs explicit user direction |
| 4 | Assume the runtime offers an interactive ask mechanism | The harness raises a clarifying question abstractly; the runtime decides how to surface it |
| 5 | Hard-code a receiver name (e.g., `hook-kit:bash-guard`) in this topic body | Use the abstract `--guard=<skill>:<topic>` dispatch contract |

## Self-check (HARD STOP — at every guard checkpoint)

1. Is the proposed operation in the default denylist? (If yes, require explicit user authorization with the exact target)
2. Does the observed effect stay inside the scope source's natural surface? (If no, block and report drift)
3. Is the instruction unambiguous in this turn? (If no, raise a clarifying question; do not guess)
4. If a `--guard=<skill>:<topic>` receiver is supplied, did you consult it in addition to the built-in floor?

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--denylist=<glob>` | conservative built-in list | Extend the denylist with custom patterns |
| `--scope-source=<path>` | `{user-request}` | Override the scope-check anchor |
| `--guard=<skill>:<topic>` | (none) | Richer guard machinery (composed on top of the built-in floor) |
| `--allow=<command-id>` | (single-use) | Mark a specific operation as authorized for the current turn |

## Output

| Output | When |
|--------|------|
| Block report (operation + target + reason) | On denylist hit |
| Scope drift report (file + reason) | On scope-check fail |
| Clarifying question | On ambiguous instruction |
| Guard pass (silent) | When all checks pass |

## Related

- `pipeline` — guardrails check at the entry of stages 3, 4, 5
- `recovery` — when a guard blocks execution mid-run, `recovery` decides retry vs. fallback
- `skill-kit/portability` — abstract dispatch contract for the `--guard` flag
