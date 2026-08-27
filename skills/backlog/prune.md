# Prune — P2/P3 Demotion to TODO Backlog

Prunes and demotes lower-priority tasks (`P2` and `P3`) from active sections (`## Priority Tasks`, `## Deep Tasks`, `## Fable Target Tasks`) into the `## TODO` backlog, preventing active execution bloat while preserving all task metadata verbatim.

## Why

Active execution sections are designed for immediate focus (current cycle/session items). Over multiple iterations:

- `P2` (next session) and `P3` (nice-to-have) items accumulate and dilute attention from true `P0`/`P1` blockers.
- Without pruning, active sections can bloat to dozens of items, causing cognitive overload and token bloat during pipeline passes.
- Migrating `P2`/`P3` tasks to `## TODO` preserves full context (Action, Why, How) while keeping active sections lean.

## Syntax & Target Marker Schema

The pruning engine recognizes standard priority markers across active task formats:

```markdown
- [BLOCKED:P2:external] Reviewer response on PR #43
- [BLOCKED:P3:selfable] Optional script lint cleanup
- [ ] [P2:selfable] Minor refactoring of test helper
- [ ] [INFRA-59] [P2:selfable] Fix CDN image path
```

Target priority levels:
- **P3**: Low priority / optional (highest candidate for pruning)
- **P2**: Medium priority / deferrable to later sessions

## Pruning Rules & Parser Discipline (HARD STOP)

To prevent priority inversions, false positives, and unintended task demotions, the pruning engine strictly enforces the following parser rules:

### 1. Task Marker Prefix Anchoring (HARD STOP)
Matching MUST anchor strictly to the task marker prefix at the start of the line (`^-\s*\[...`).
- Valid prefix examples:
  - `^-\s*\[(?:BLOCKED:)?(P[23])(?::([^\]]+))?\]`
  - `^-\s*\[[ x/]\]\s*\[(?:BLOCKED:)?(P[23])(?::([^\]]+))?\]`
  - `^-\s*\[[ x/]\]\s*(?:\[[A-Za-z0-9_-]+\]\s*)+\[(?:BLOCKED:)?(P[23])(?::([^\]]+))?\]`

### 2. P0 / P1 Early Exclusion Guard (HARD STOP)
Any task bearing a `P0` or `P1` priority prefix MUST NEVER be classified as a candidate or pruned.
- The parser must inspect the prefix for `P0` and `P1` (e.g. `[BLOCKED:P0:...]`, `[BLOCKED:P1:...]`, `[ ] [P1]`) and immediately skip matching before evaluating candidate rules.

### 3. Prohibit Unanchored Prose Scanning (HARD STOP)
Never use unanchored regex searches like `\b(P[23])\b` across the entire line text.
- Inline historical notes (e.g. `[Fable P3 seminar notes]`, `*(P2→P1 escalated)*`) or bracketed URLs in description text must NOT trigger a `P2`/`P3` match on an otherwise `P1` task.

| # | Don't | Do |
|---|-------|-----|
| 1 | Scan the entire line for `\b(P[23])\b` | Anchor priority detection strictly to the line start (`^-\s*\[...`) |
| 2 | Demote `[BLOCKED:P1:external]` containing "P3" in prose | Exclude `P0`/`P1` items upfront via an early exclusion guard |
| 3 | Truncate Why/How sub-bullets during migration | Move the entire multi-line task block verbatim to `## TODO` |

## Scoring & Demotion Order

When pruning with a limit (`--limit N`), candidate tasks are scored and prioritized for demotion:

| Criteria | Condition | Score Weight | Rationale |
|----------|-----------|:------------:|-----------|
| **Priority** | `P3` vs `P2` | `+30` (P3) / `+20` (P2) | Lower priority demoted first |
| **Classification** | `external` vs `selfable` | `+10` (external) / `+0` (selfable) | Blocked external waits demoted before actionable code work |
| **Section** | `## Priority Tasks` vs `## Deep Tasks` | `+5` (Priority) / `+0` (Deep) | Top-level queue slimmed before deep analysis queue |

## Dry-Run & Anomaly Post-Analysis (HARD STOP)

Running `--dry-run` is a pre-flight inspection gate, not a passive text printout.

1. **Mandatory Post-Analysis**: After executing a dry-run, the agent must perform anomaly verification:
   - Check for false positives or priority inversions (e.g., misclassified P1 items).
   - Check for active tooling/guard bug fixes (e.g. active false-positive fixes that should remain in flight).
2. **Automated Anomaly Warnings**: The CLI script flags any candidate containing `P0` or `P1` tokens in its body, or active tooling keywords, emitting an explicit warning banner in the dry-run output.

## CLI Usage

The prune workflow is executed via `prune_p2p3.py`:

```bash
# Preview candidates across all workspace trackers without modifying files
python scripts/prune_p2p3.py --all --dry-run

# Limit candidate preview to top 10 items for a specific tracker
python scripts/prune_p2p3.py --file .agents/fix_plan.md --limit 10 --dry-run

# Physically execute migration (moves items to ## TODO and prunes from active sections)
python scripts/prune_p2p3.py --all
```

Invoked via the fix-plan skill:

```bash
/fix-plan --prune-p2p3 --dry-run --all
/fix-plan --prune-p2p3 --limit 10
```
