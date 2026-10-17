# Enforce Markers

Declare a MANDATORY skill-call step so the generic `check-enforce-markers.py`
Stop hook (and its `check-enforce-markers-next-turn.py` UserPromptSubmit
backstop) can catch it being skipped — without writing a new bespoke hook
script per violation.

## Syntax

Same-turn requirement (a skill must call another skill before/during a
specific step):

```
<!-- enforce: requires-skill-call="<skill-name>" trigger="<substring that appears in the assistant's own turn text when this step is reached>" scope="same-turn" -->
```

Completion-triggered requirement (finishing some other action must be
followed by a specific skill call):

```
<!-- enforce: on-completion="<substring that appears when that action completes>" requires-skill-call="<skill-name>" scope="next-turn" -->
```

## Rules

- `scope="same-turn"` is checked by the Stop hook before the turn ends — a
  violation blocks.
- `scope="next-turn"` is checked by the UserPromptSubmit backstop one turn
  later — a violation is advisory only (it cannot block, since the required
  call's window has already passed).
- `trigger`/`on-completion` text should be a substring that is specific
  enough not to appear in ordinary unrelated prose. Prefer quoting a phrase
  already used in your skill's own step heading or completion message —
  see `skills/consolidate/collect.md`'s Step 3.6 marker for a worked
  example (its trigger is lifted verbatim from the step's own "Follow it
  for every feedback item in Step 4 (classify)" text).
- Malformed markers (missing `requires-skill-call` or `scope`) are silently
  skipped (fail-open) — verify your marker is being picked up by running:

  ```bash
  python3 -c "
  import importlib.util
  spec = importlib.util.spec_from_file_location('m', 'skills/hook-kit/scripts/parse_enforce_markers.py')
  m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
  print(m.parse_markers('<your-file>.md'))
  "
  ```

## Scope limitation

This mechanism only covers *skill-call sequence* requirements. Content-format
requirements (e.g. "this output column must include an emoji prefix") are a
different kind of check and belong in a dedicated vocabulary/format hook —
see `block-summary-status-vocab.py` for that pattern instead.

## Implementation

- `scripts/parse_enforce_markers.py` — marker parser
- `scripts/build_enforce_registry.py` — mtime-cached registry across all enabled skills
- `scripts/match_enforce_triggers.py` — transcript-vs-registry matcher
- `scripts/extract_current_turn_text.py` — turns a session JSONL into matchable text
- `resources/check-enforce-markers.py` — Stop hook entrypoint (same-turn, blocking)
- `resources/check-enforce-markers-next-turn.py` — UserPromptSubmit entrypoint (next-turn, advisory)
