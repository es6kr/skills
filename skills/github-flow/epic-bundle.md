# Epic Bundle — Deferred Review Findings → One Epic Issue

Bundle **deferred review findings** scattered across multiple PRs into a single **Epic tracking issue**: one issue with a checklist body, native sub-issue relationships for any split-out work, and an `epic` label. This turns a pile of "fix later" review items into one assignable, trackable unit (a checklist Epic).

## When to Use

- After several PRs merged, each leaving non-blocking `[REVIEW_FEEDBACK]` findings deferred for later
- When the deferred items span 2+ PRs and would otherwise be lost in scattered tracking entries
- When a maintainer wants a single hand-off artifact a junior/teammate can pick up (flexible split)

### Triggers

| Trigger | Source |
|---------|--------|
| Explicit call | User names the PRs to bundle (e.g., "bundle the deferred findings from #A #B #C into an epic") |
| Auto-suggest | `consolidate` next step proposes this when deferred findings accumulate across N+ PRs (see consolidate → next). The suggestion is an offer, not an auto-run — issue creation still needs explicit user approval (see Rules) |

## Input Sources

Findings are collected from two media, **checklist first, PR comments as supplement**:

| Source | What | Priority |
|--------|------|----------|
| Deferred-tracking checklist | The local checklist where `[REVIEW_FEEDBACK]` deferred items were already recorded (one line per finding, PR-tagged) | Primary — reuse the already-classified entries |
| PR review comments | The Internal Review / AI Review Summary comments on each PR | Supplement — catch findings not yet written to the checklist |

> The deferred-tracking checklist is a local-only artifact. Per Core Rule #2, **never** name its path in the Epic body — describe items by their content, not their checklist location.

## Procedure

### Step 1: Gather Deferred Findings

For each target PR:

1. Read the deferred-tracking checklist entries tagged with that PR (primary source).
2. Fetch the PR's review comments as a supplement to catch un-recorded findings:
   ```bash
   GH_TOKEN="$(gh auth token --user <account>)" gh pr view <PR> -R <owner>/<repo> --comments
   ```
3. Build a flat finding list. For each finding keep: `{pr, severity, type, title, file:line, author-or-ownership}`.

### Step 2: Dedup + Group

- **Dedup**: drop findings already resolved by a later merged PR (cross-check the checklist for `[x]`/resolved markers). Same-file+same-line duplicates collapse to one.
- **Group by source PR (primary)**: the checklist body is organized under one section per source PR, so the PR ref lives once in the section header (autolinked) and never repeats inline on each line. Do NOT group the checklist by theme — theme groups mix PRs and force a per-line `(#PR)` token.
- **Theme is secondary (prose only)**: capture cross-PR themes separately for the "Suggested grouping" prose block, which informs the split without polluting the checklist.

### Step 3: Confirm Scope + Split (AskUserQuestion)

Present the bundle and let the user decide the split shape (mirrors a "flexible split" epic):

```text
AskUserQuestion {
  question: "<N> deferred findings across <PRs>. How should the Epic be split?",
  multiSelect: false,
  options: [
    { label: "Single Epic checklist (Recommended)", description: "One issue, all findings as a checklist. Splitting into child PRs is left to whoever picks it up" },
    { label: "Epic + grouped sub-issues", description: "One Epic + native sub-issues per theme group (uses dependencies/addSubIssue)" },
    { label: "Adjust grouping", description: "Re-cluster before creating" }
  ]
}
```

Ownership note: findings on **another author's branch** are tracked in the Epic checklist but stay comment-only on the PR itself (branch ownership boundary). Mark such items so the picker knows they need the author or a fresh branch.

### Step 4: Create the Epic Issue

Build the Epic body via the **plan-to-issue** topic (MD → issue body), then create the issue. Run the **register** topic first to avoid duplicating an existing Epic.

Epic body shape — **group findings under per-PR section headers** so the source PR ref appears once (autolinked) in the header, never repeated inline on every checklist line:

```markdown
## Background

Consolidated deferred review findings from #<PR-a>, #<PR-b>, #<PR-c> (non-blocking, deferred at merge time).

## Findings (flexible split — bundling/splitting into PRs is the picker's call)

### #<PR-a> — <theme summary> (@<author>)

- [ ] 1. <severity> <type>: <title> — `<file>:<line>`
- [ ] 2. <severity> <type>: <title> — `<file>:<line>`

### #<PR-b> — <theme summary> (@<author>)

- [ ] 3. <severity> <type>: <title> — `<file>:<line>`

## Suggested grouping (prose — cross-PR theme combos for the picker)

- <theme X> (items 1, 3) → recommended combined PR
- <theme Y> (item 2) → standalone

## Verification

Each finding's PR carries its own test plan; this Epic closes when every checklist item is resolved (or explicitly de-scoped).
```

- **Hoist the PR ref to the section header, not every line** — a section header `### #<PR> — <theme>` autolinks the PR once and reads cleanly; repeating `(#<PR>)` on every checklist item is per-line noise that degrades readability.
- **Use bare `#N`** for real PR/issue references in headers and prose (GitHub autolinks them); use plain `1.`/`2.` finding numbers as list labels, never bare `#N` that would cross-link unrelated issues.
- **Sanitize** the body before posting (PUBLIC repos) — run the `sanitize` topic.
- `gh issue create` requires **explicit user approval** (see Rules). Create with `--label epic`:
  ```bash
  GH_TOKEN="$(gh auth token --user <account>)" gh issue create -R <owner>/<repo> \
    --title "[Epic] <theme> — deferred review findings from #<PR-a>/#<PR-b>/#<PR-c>" \
    --body-file <epic-body.md> --label epic
  ```
  If the `epic` label is missing, create it first (`gh label create epic --color 7B68EE`).

### Step 4.5: Optional Visualization Dispatch (many-PR bundles)

For a bundle spanning many source PRs, the per-PR-section checklist (Step 4) can get hard to scan. Offer a **d3 force-directed render** of the Epic structure as an additional, opt-in deliverable — reusing the same abstract `--render=<skill>:<topic>` dispatch contract already proven by `skill-kit/graph` and `cc-plugin/clustering` (see `skill-kit/portability` Rule B — do NOT hardcode a specific receiver).

**When to offer**: bundle spans ≥4 source PRs, or the user explicitly asks for a visual. Below that threshold the markdown checklist stays clearer and cheaper — this is additive, never a replacement for Step 4's body.

**Schema mapping** (caller transforms Epic data into the receiver's `{groups, skillHubs, topics, links}` schema):

| Epic element | Schema field |
|---|---|
| Epic issue | one `skillHubs` node (the hub) |
| each source PR | a `topics` node, `owner: <Epic hub id>` (auto-generates the membership link) |
| finding count on that PR | `links[].weight` (clamp to the schema's 1–10 range) |
| theme summary (Step 2 "Suggested grouping") | `links[].note` |

**Dispatch**:

```bash
/github-flow epic-bundle <PRs> --render=<receiver-skill>:<receiver-topic>
```

When the flag is supplied, invoke the receiver with the transformed JSON after Step 4 (Epic body already built) and report the rendered HTML path alongside the issue URL. When omitted, the procedure stops at the markdown Epic body — no visualization step runs.

#### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Default this on for every bundle | Offer it only when the PR count crosses the threshold, or on explicit request — small bundles are cheaper as a checklist |
| 2 | Hardcode a specific render receiver in this topic body | Use the abstract `--render=<skill>:<topic>` flag — caller chooses the receiver (`skill-kit/portability` Rule B) |
| 3 | Treat the render as a second SSOT for Epic state | The rendered HTML is a point-in-time snapshot of the Epic body at dispatch time, not a live view — re-dispatch after significant body edits if a fresh render matters |

### Step 5: Sub-issues (only if "Epic + grouped sub-issues" chosen)

For each child issue, use the **dependencies** topic Sub-issue Procedure (`addSubIssue`) to create the native parent-child relationship — a `- #N` body link alone is not enough.

### Step 6: Cross-reference Back

- Update the deferred-tracking checklist: replace the scattered per-PR deferred lines with a single pointer to the Epic issue number, so future scans see them as bundled (not unbundled).
- If any finding was resolved by a merged PR during gathering, map it `[x]` in the Epic body with the resolving PR number.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Name the internal deferred-tracking checklist path in the Epic body | Describe findings by content; the checklist is local-only (Core Rule #2) |
| 2 | `gh issue create` autonomously because findings exist | Issue creation needs explicit user approval (`git.md` "no autonomous issue create"). The auto-suggest is an offer only |
| 3 | Wrap real PR/issue refs in backticks (`` `#N` ``) | Bare `#N` so GitHub autolinks; use `1.` labels for finding numbers to avoid stray cross-links |
| 3a | Repeat `(#PR)` inline on every checklist line (group by theme → mixes PRs) | Group the checklist by source PR; hoist the `#PR` to the section header once (autolink, clean). Inline per-line PR ref is readability noise |
| 4 | Add only `- #N` body links and call sub-issues done | Create native relationships via `addSubIssue` (dependencies topic) |
| 5 | Bundle another author's branch findings as actionable in our scope | Track in the Epic checklist but flag as author-owned (comment-only on their PR) |
| 6 | Re-bundle findings already resolved by a merged PR | Dedup against resolved/`[x]` markers in Step 2 first |
| 7 | Post the Epic body to a PUBLIC repo without scanning | Run `sanitize` before `gh issue create` |

## Self-check (before `gh issue create`)

1. Did the user explicitly approve creating the issue? If no → stop, ask.
2. Is the body free of internal checklist paths and any personal data (sanitize passed)?
3. Are all real PR/issue refs bare `#N` (not backticked)?
3a. Is the checklist grouped by source PR (PR ref in section header), with **no inline `(#PR)`** repeated on each line?
4. Are resolved findings already mapped `[x]` (not re-bundled as open)?
5. Does the title carry `[Epic]` + the source PR numbers, and is `--label epic` applied?

## Related

- `plan-to-issue.md` — builds the Epic body (MD → issue body)
- `register.md` — duplicate-Epic check before create
- `dependencies.md` — Sub-issue Procedure (`addSubIssue`) for the grouped-sub-issues split
- `sanitize.md` — HARD STOP personal-data scan before posting
- `consolidate` next step — emits the auto-suggest that routes here
- `skill-kit/graph.md` / `cc-plugin/clustering.md` — the `--render=<skill>:<topic>` abstract dispatch contract Step 4.5 reuses
- `es6kr-graph` — the standalone D3-force receiver this repo already has for the schema in Step 4.5
