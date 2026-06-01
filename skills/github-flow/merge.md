# Merge

Perform a final quality check on a PR (CI / Review), then merge and clean up the commit message according to the rules.

## When to Use

- On requests like "merge the PR", "confirm reviews and merge", "merge if CI passed"
- When integrating a fully implemented and reviewed PR into the main branch
- Whenever you want a final, pre-merge sanity check on CI success and AI-review actionable status

## Merge condition checks (every condition must pass)

**Even when supervising / reporting, check these first** — never ask "shall we merge?" on a PR that does not satisfy the conditions.

### 1. CI success (real-time)

```bash
gh pr checks <PR_NUMBER>
```
- If any `fail`, stop. If `pending`, wait.
- Required to be confirmed **in real time** — don't rely on a state recorded in fix_plan.

### 2. AI Review Summary — every Actionable item addressed

**Default procedure (HARD STOP — strict order)**:

0. **Verify a real Copilot review error** (explicit error keywords only — beware of false positives):

   ```bash
   gh pr view <PR_NUMBER> --json reviews -q '.reviews[] | select(.author.login == "copilot-pull-request-reviewer") | select(.body | test("encountered an error|unable to review"; "i")) | {state, bodyLen: (.body | length)}'
   ```

   - Result empty → proceed to Step 1 (a short body or the absence of a "Reviewed changes" section may still be a normal review on a simple PR — do NOT flag a false positive)
   - Result matched → real error → re-request Copilot (`gh pr edit <PR_NUMBER> --add-reviewer copilot-pull-request-reviewer`) → wait for the normal review to arrive, then proceed to Step 1

   **Forbidden**: declaring a partial failure just because the `Reviewed changes` section is missing or the bodyLen is short. Copilot does post short reviews to simple PRs (e.g. PR #110 merged, bodyLen 2040, inline comments only, no `Reviewed changes` section).

1. **Check whether the AI Review Summary comment exists**:
   ```bash
   gh api repos/{owner}/{repo}/issues/<PR_NUMBER>/comments --jq '.[] | select(.body | startswith("## AI Review Summary"))'
   ```

2. **No Summary comment → unconditionally auto-invoke `/consolidate pr-review`**:
   - **If any AI review (CodeRabbit / Copilot / etc.) is present, consolidate is the default** — not optional
   - After consolidate, confirm the Summary comment was posted → continue to Step 3
   - **Forbidden**: asking the user a merge / apply option without the Summary. consolidate must run first

3. **Summary comment exists → count 🔴 Critical (HARD STOP)**:

   ```bash
   # Count 🔴 Critical entries in the Summary body
   gh api repos/{owner}/{repo}/issues/<PR_NUMBER>/comments \
     --jq '.[] | select(.body | startswith("## AI Review Summary")) | .body' \
     | grep -c '🔴 Critical'
   ```

   - **🔴 Critical ≥ 1 → merge is absolutely forbidden**. Address the Critical items in code, then refresh the Summary before merging. "deferred" is not allowed — Critical items must be addressed
   - 🔴 Critical 0 + `Actionable > 0` not yet addressed → use AskUserQuestion to confirm the action (apply / deferred / skip)
   - If everything is addressed or explicitly deferred, continue to Step 2.5

**Forbidden patterns**:
- ❌ AI review exists, but you bypass consolidate and ask the user to merge directly
- ❌ Interpreting "if no Summary, run consolidate" as "you can skip it"
- ❌ Looking only at CodeRabbit and missing the Copilot review (both must be consolidated)

### 2.5. Verify deferred Actionable items are registered in a tracking medium (HARD STOP)

**If ≥1 Actionable items are explicitly marked "deferred" on the Summary, before merging, verify they are registered as `[BLOCKED]` in a tracking medium.** If not registered, block the merge.

#### Verification procedure

1. **Identify deferred items**: count items decided as deferred on the Summary body (e.g. "🟡 Minor (optional)", "🟡 Minor (No action)", "🔴 Critical not addressed")
2. **Verify tracking-medium registration** (per environment):

   ```bash
   # Ralph environment
   grep -cE '\[BLOCKED\].*\[REVIEW_FEEDBACK\].*PR #<N>' {workspace}/.ralph/fix_plan.md

   # checklist environment
   grep -cE '\[BLOCKED\].*PR #<N>' {workspace}/checklist.md

   # GitHub Issue environment
   gh issue list --search "deferred from PR #<N>" --state open --json number
   ```

3. **Compare counts**: deferred-item count ≤ medium-registration count → proceed. deferred-item count > medium-registration count → block the merge

#### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat the "deferred" tag in the Summary table as registration | The Summary is a one-shot GitHub comment. Registration in a medium (fix_plan / checklist / Issue) must be verified separately |
| 2 | Interpret "if deferred is stated, merge is allowed" as "merge regardless of medium registration" | Merge requires BOTH explicit deferred + medium registration |
| 3 | On missing registration, ask the user "shall I register?" via options | `consolidate/pr-review.md` Step 7.6 handles auto-registration. Missing = consolidate-procedure violation → re-invoke consolidate, then re-verify |
| 4 | Treat a "we'll register when the user picks merge" promise as actual registration | A promise ≠ an action. Decide based on actual lines existing in the medium file |

#### Self-check (every time, before merging)

1. Is there ≥1 deferred Actionable item on the AI Review Summary?
2. If yes, did you check medium-registration counts with grep / gh per environment?
3. Did you confirm `deferred count = registered count`? (Block on mismatch)
4. Did you include the registration medium path / Issue number in the merge decision report?

### 3. Test Plan — per-category merge guard

Apply the PR-body Test Plan category classification rule (pr.md "Test Plan category classification" section) at merge time. Guards differ by category prefix (`[general]` / `[UI]` / `[post-merge]`).

```bash
gh pr view <PR_NUMBER> --json body
# Or chain a project-local verification script:
gh pr view <PR_NUMBER> --json body --jq '.body' | node scripts/check-test-plan.js
```

| Category prefix | Guard when unchecked |
|-----------------|----------------------|
| `[general]` | **Cannot merge** (HARD STOP, no exception) |
| `[UI]` | **Cannot merge** (HARD STOP, no exception) |
| `[post-merge]` | **Merge allowed** (but tracking-medium registration must be verified — procedure below) |
| No prefix (legacy) | Treated as `[general]` or `[UI]` — **cannot merge** |

#### `[post-merge]` items — verify tracking-medium registration (HARD STOP)

If ≥1 `[post-merge]` items exist, confirm they are registered in a tracking medium before merging:

```bash
# Extract [post-merge] items from the PR body
gh pr view <PR_NUMBER> --json body --jq '.body' | grep -E '^\- \[.\] \`\[post-merge\]\`'

# Verify each item names a tracking link (issue # or fix_plan path)
# 0 items without a tracking link is required to merge
```

| # | Don't | Do |
|---|-------|-----|
| 1 | `[post-merge]` item without a tracking medium → post-merge verification gets dropped | Inline `(tracking: gh issue #N)` or `(tracking: fix_plan.md [BLOCKED])` in the item description before merging |
| 2 | Misclassify essential validation as `[post-merge]` to bypass the merge guard | Apply the "essential vs adjacent follow-up" self-check — essential validation belongs to `[general]` / `[UI]` |

Legacy PRs (Test Plan without category prefix): the existing HARD STOP applies — if even one `- [ ]` is unchecked, you cannot merge. For items not executable before merge, change to a tracking annotation like `- [x] (verify post-deploy — tracked in issue #N)` + AskUserQuestion approval (but NEVER use the tracking annotation to bypass essential validation).

A PR with no Test Plan is unaffected by this condition.

### 3.5. Blocked by — all predecessor issues CLOSED (HARD STOP)

If the issue this PR closes (or the PR itself) has GitHub Issue Dependencies (`blockedBy`) set, **every predecessor issue must be CLOSED** to merge. See [dependencies.md](./dependencies.md) for details.

```bash
# Extract issues the PR closes (Closes/Fixes keywords + linked issues)
gh pr view <PR_NUMBER> --json closingIssuesReferences -q '.closingIssuesReferences[].number'

# For each soon-to-close issue, query blockedBy
GH_TOKEN="$(gh auth token --user <account>)" gh api graphql -f query='
  query { repository(owner:"<owner>", name:"<repo>") {
    issue(number:<N>) {
      blockedBy(first:10) { nodes { number state title } }
      issueDependenciesSummary { totalBlockedBy }
    }
  } }
'
```

**Decision rule**:

| `blockedBy` node state | Action |
|------------------------|--------|
| All `CLOSED` | OK — can merge |
| ≥1 `OPEN` | **Cannot merge** — report the OPEN predecessor's number + title, ask via AskUserQuestion (e.g. "predecessor issue #N is unresolved. How shall we proceed?") |
| `blockedBy` empty | OK — no dependencies |

**Forbidden patterns**:
- ❌ Merging on your own judgment "it's unrelated" when `blockedBy` has an OPEN issue
- ❌ Force-closing the predecessor at the last minute then merging (actual work incomplete)

**If the predecessor will soon be closed by another PR**: re-order so this PR merges after that PR. Use AskUserQuestion to get the user's decision.

#### Distinguish PR essential validation vs adjacent follow-up validation (HARD STOP)

When marking an unchecked Test Plan item as `[x] (post-merge verification — tracked separately)`, **always self-check the essential vs adjacent classification**. Do not use the tracking annotation to bypass essential validation.

**Classification rule**:

| Class | Definition | Handling |
|-------|------------|----------|
| **PR essential validation** | The goal stated in the PR title / body. This validation must SUCCEED for the PR to truly solve the problem | **Must verify before or immediately after merge.** Tracking annotation `[x]` is forbidden |
| Adjacent follow-up | A byproduct of the PR change. Environment impact, regression monitoring, etc. | Tracking annotation `[x]` is allowed |

**Self-check procedure (right before marking a Test Plan item as `[x]` tracking)**:
1. Extract the PR's core goal in one sentence ("the essence of this PR is solving X")
2. Determine whether the unchecked item is a direct verification of X:
   - "X workflow SUCCESS check" / "X behavior verified" / "X passed" → **essential validation**
   - "environment impact monitoring" / "regression tracking" / "follow-up PR work" → adjacent follow-up
3. If essential → do NOT mark `[x]`. Consider triggers that can be executed before or immediately after merge:
   - manual `workflow_dispatch`
   - cross-repo trigger (e.g. PAT-authenticated `repository_dispatch`)
   - real user-scenario reproduction (curl, Playwright)
4. If no immediately-executable trigger → **do not merge**. Use AskUserQuestion only to decide "how to verify". Merging while unchecked is absolutely forbidden

**Correct flow** (essential validation):
1. If the unchecked item is essential → attempt a trigger before merge (e.g. manual workflow_dispatch + watch, infra dry-run, curl)
2. After SUCCESS, check `[x]` → merge
3. If a trigger is impossible → **do not merge**. Decide a verification approach with the user, execute it, check `[x]`, then merge

**Absolutely forbidden (2nd recurrence — HARD STOP strengthened)**:
- The "merge with unchecked items after user consent" path is closed. Even if the user says "go ahead", do not run `gh pr merge` while any `- [ ]` remains
- "Record and proceed" = "record this fact" + "proceed to the next step (verification / deploy)", NOT "approval to merge unchecked"

#### HARD STOP — Self-check for the merge-option AskUserQuestion (five conditions)

Before recommending merge (AskUserQuestion option includes "proceed merge" / "squash merge"), **self-check all five conditions**:

| # | Condition | How to verify | If not satisfied |
|---|-----------|---------------|------------------|
| 1 | All CI PASS | `gh pr checks <N>` → confirm bucket=pass | Exclude "merge" from options |
| 2 | All Test Plan `[x]` | `gh pr view <N> --json body --jq '.body' \| node scripts/check-test-plan.js` → exit 0 | Exclude "merge" from options |
| 3 | AI Review Summary comment posted | `gh pr view <N> --json comments` → confirm a user-authored "AI Review Summary" body | consolidate invocation required |
| 4 | Mergeable | `gh pr view <N> --json mergeable` → MERGEABLE | Resolve conflicts first |
| 5 | Cross-repo infrastructure dependency | Inspect PR body / code for cross-repo env-var or infrastructure changes | Block merge until the dependent repo's change is merged + deployed |

**Condition 5 in detail — cross-repo dependency (HARD STOP)**:
- The code references a new env var (`process.env.X`, `lookup('env', 'X')`) that is supplied by an infra repo's inventory / template
- **The infra-repo PR must be merged + deployed first** before the app code can merge
- Order: infra variable-addition PR merged → infra deploy → app code PR merged → app deploy
- **Forbidden**: merging the app code first and deferring the infra as a "follow-up PR" — at deploy time the missing env var breaks the feature

**If even one condition is unsatisfied, ALL of the following are forbidden**:
- Including "proceed merge" / "squash merge" / "merge recommended" in AskUserQuestion options
- Bypassing unsatisfied conditions with phrases like "Playwright will run separately", "ZAP will follow", while still recommending merge
- Concluding "the core passed, so merge is fine" on your own judgment
- Concluding "AI bot comments exist, so OK" on your own (the consolidate Summary is separate)

#### CI fail — analyze the essence + state the merge value (HARD STOP)

Before recommending merge on a PR with CI fails, **state both**:

1. **Essence analysis of each CI fail (self-check per fail entry)**:
   - **Is the fail resolved by this PR?** → if so, wait until it passes, then merge
   - **Is the fail unrelated to this PR?** → register a separate issue + name the issue in the PR body + guarantee the fail is not permanently masked by this PR
   - **Is the fail intentional `continue-on-error`?** → record the GUARD reason in the PR body + name a separate tracking issue

2. **Merge value (diff with merging vs not merging)**:
   - What changes between pre-merge and post-merge? (code coherence, regression prevention, unblocking subsequent work — concretely)
   - If merging is not strictly required, deferral may be a better option — if the value is unclear, offer a defer option

**Forbidden pattern** (no statement of "what got better" from the user's POV):
- ❌ 2 CI fails → "continue-on-error / tracked separately" → recommend merge. No value statement
- ❌ Abstract phrasing like "merging restores env coherence with the master fixture". State concrete changes
- ❌ Treating fails as "deferred" without a separate tracking issue and merging — tracking lost

**Correct flow** (PR with CI fails):
1. Report the essence-analysis result text per fail
2. On detecting "fails this PR does not resolve" → **prefer reusing an existing tracking issue** (Step 2-A) → if none, register a new issue (Step 2-B)
3. State the merge value in one line (concrete): "Merging makes the master fixture use `service-A-source` → prevents regressions in the next PR + guarantees coherence at dev-A/integration/production rollout"
4. Then issue AskUserQuestion or auto-merge

**Step 2-A: prefer reusing an existing issue (HARD STOP)**

Before suggesting a new issue, search:

```bash
# 1. PR trigger issue (look at Resolves / Relates to / Closes keywords in the PR body)
gh pr view <PR> --json body -q '.body' | grep -iE 'Resolves|Relates to|Closes|Fixes' | head

# 2. Open issues with the same label / area
gh issue list -R <owner>/<repo> --state open --label <label> --json number,title

# 3. Existing issues by fail keyword
gh search issues "<fail keyword>" --repo <owner>/<repo> --state open
```

**Decision**:
- If a trigger issue exists and the fail falls in its scope → **add the unresolved item to the trigger-issue body** (do not close; reopen or leave as-is)
- If an open issue in the same area is found → **add the fail item to that issue body**
- If no search hits → register a new issue (Step 2-B)

**Forbidden pattern**:
- ❌ Suggesting a new issue without checking the trigger issue. The same environment inconsistency ends up split across issues with fragmented tracking
- ❌ When `Resolves #N` is stated in the PR, suggesting a new issue after solving only part of it → adding the unresolved item to `#N`'s body is the canonical fix

**Step 2-B: register a new issue (only when no existing issue applies)**

Use `/github-flow plan-to-issue` or `gh issue create`.

**Correct flow** (on any unsatisfied condition):
1. Test Plan unchecked → run verification directly → check `[x]`
2. AI Review Summary missing → invoke the consolidate skill → Summary posted → actionable addressed
3. CI failure → root-cause analysis + fix
4. Conflicts → resolve conflicts
5. Only after all four are satisfied may you offer a merge option. Merge only when the user explicitly says "merge now" (auto-recommendation is forbidden)

#### Pre-approved context — skip AskUserQuestion (auto-merge)

When all four merge conditions are satisfied AND **the user pre-approved a workflow that includes merging**, skip AskUserQuestion and run squash merge immediately. Asking again is redundant and delays progress.

**Pre-approval patterns** (the user's answer / instruction contains expressions like):
- "wait for the predecessor PR to merge" / "proceed after the PR merges" / "next step after merge"
- "merge if conditions are satisfied" / "merge once CI passes" / "squash once it passes"
- "handle the preliminary work" + the workflow includes a merge step
- "run it through to the end" / "do it all in one go" + the workflow is named

**❌ Non-pre-approval patterns (HARD STOP — do not auto-recommend the merge option)**:

The following expressions mean "inspect / review / check" — NOT permission to merge. Even if a merge keyword appears in the option description, auto-recommending merge is a violation:

- "review merge conditions" / "check merge conditions"
- "see if mergeable" / "look into whether it can merge"
- "inspect conditions" / "review" / "check" / "inspect" (when used alone)
- A merge word in the option description, when the verb is "review / check / inspect / look", is not approval
- The user must add an explicit **action verb** like "then merge" / "merge once it passes" / "proceed when conditions hold"

**Decision rule (option self-check)**:

| User answer / option phrasing | Intent | Auto-recommend the merge option |
|-------------------------------|--------|---------------------------------|
| "merge if conditions are satisfied" | Approval (conditional action) | ✅ auto-merge or recommend the option |
| "merge after CI passes" | Approval | ✅ |
| "review merge conditions" | Non-approval (inspect) | ❌ exclude merge from options; offer "report conditions only" |
| "check if mergeable" | Non-approval (inspect) | ❌ |
| "inspect conditions" | Non-approval (inspect) | ❌ |
| "run it through to the end" + workflow names merge | Approval | ✅ |

**Correct flow** (non-approval pattern + conditions satisfied):
1. Report the five-condition self-check result as text ("CI ✅, AI Review ✅, Test Plan ✅, Mergeable ✅")
2. Use AskUserQuestion to **confirm merge intent separately** — "All conditions satisfied. Proceed with merge?" (options: "merge now" / "defer" / "additional review")
3. Run `gh pr merge --squash` only when the user picks "merge now"

**Auto-merge procedure**:
1. Self-check the five conditions (CI / Test Plan / AI Review Summary / Mergeable)
2. If all satisfied → skip AskUserQuestion, run `gh pr merge --squash`
3. If any unsatisfied → AskUserQuestion explaining the blocker + suggesting how to clear it (independent of pre-approval)

**Forbidden patterns**:
- "Wait for the predecessor PR to merge" answer → after the PR is created + five conditions satisfied → asking "shall I merge?" again (redundant)
- Mis-interpreting a pre-approval answer as "inspect intent" instead of "merge intent"

### 4. Mergeable status

```bash
gh pr view <PR_NUMBER> --json mergeable
```
- If `CONFLICTING`, resolve conflicts first.

### Per-repository Formal Review policy

| Repository profile | Self-approve | Formal Review |
|--------------------|--------------|---------------|
| Org-protected app repo | Not allowed | **Skip** — replaced by CI + AI Review + Test Plan |
| Solo-maintained infra repo | Allowed (solo) | Replaced by AI Review APPROVE |

- For an org-protected app repository where self-approve is not allowed, the formal-review condition is skipped.
- If all five conditions above pass, the PR can be merged.

## Merge Execution

### Squash Merge (recommended)

Most feature work / bug fixes use squash merge. Clean up the commit message per the rules:

1. **Subject**: start from the PR title with redundant tags (e.g. `[WIP]`, `[DRAFT]`) removed.
2. **Body**:
   - Distill the key content from the PR body's "Changes" or "Key changes" section.
   - Include `Closes #issue` or `Fixes #issue`.
   - On a PRIVATE repo you MAY add a non-sensitive trace reference (e.g. a short workspace identifier) if your team relies on one. On a PUBLIC repo, **do not embed session identifiers / personal handles / internal IDs** — they survive in `git log` forever and violate the sanitize HARD STOP introduced elsewhere in this skill.

```bash
# Example (PUBLIC repo — no internal identifiers in the squash body)
gh pr merge <PR_NUMBER> --squash --subject "feat: add user session countdown UI" --body "- JWT-exp-based countdown hook and header UI\n- Closes #253"
```

### Regular Merge (merge commit)

Use only when preserving commit history matters (e.g. merging large deploy branches).

```bash
gh pr merge <PR_NUMBER> --merge
```

## Rules

- **Always confirm**: `gh pr checks` right before merging is non-optional.
- **Message quality**: at squash time, write a message that actually reveals the work — not GitHub's default "Merge pull request #..." text.
- **Post-merge cleanup**: after a successful merge, delete the local branch and check the corresponding `fix_plan.md` item as `[x]`.
- **Update related issue body checklists (HARD STOP)**: if the PR referenced an issue via `Relates to #N` / `Resolves #N` / `Fixes #N` / `Refs #N`, immediately after merge update that issue body's checklist (`- [ ]`) to `- [x]` for items covered by the PR scope, and append a reference to the merged PR number. Especially for **epic-style issues** (multiple Phase 1/2/3 checkboxes), batch-update every Phase item completed by the PR merge.
  - Update format: `- [x] item description (merged in PR #N)` or `- [x] item description — PR #N`
  - Search: `gh pr view <PR> --json body -q '.body' | grep -iE 'Resolves|Relates to|Closes|Fixes|Refs'` → extract referenced issues
  - **Cross-repo issues apply equally**: if the PR references another repository's issue, update that repository's issue body too (e.g. when an app-repo PR includes work tracked in the infra repo, update both issue bodies)
  - Consequence of skipping: the epic body stays stale; on the next planning pass, "already implemented items" appear unfinished and cause duplicate work / confusion
- **Deploy follow-up**: after merge, confirm with the user whether to run the related deploy workflow (infra automation, ArgoCD sync, etc.).
- **`gh pr merge` direct invocation is absolutely forbidden** — merging must always go through this skill (`/github-flow merge`). Trying to merge without surfacing the five conditions to the user is a procedural violation.
- **Post-hoc review for PRs merged without review** — run `/consolidate pr-review` for a post-hoc review, and if actionable items appear, ask via AskUserQuestion whether to register them in a follow-up PR or an existing issue.

## Recording evidence of merge-condition satisfaction (CRITICAL)

**When you add the PR entry to the "Completed" or "Merged / Closed" section of fix_plan.md right after merging, also record the evidence for all five conditions.**

A bare `✅` leaves no basis to verify "the conditions were really satisfied" after the fact. Format:

```markdown
### PR #N (branch-name) — ✅ MERGED YYYY-MM-DD
- CI: 4/4 SUCCESS (test ubuntu, test windows, e2e, CodeRabbit)
- AI Review: CodeRabbit ✅ addressed (3 actionable), Copilot ✅ addressed (1 comment)
- Test Plan: 5/5 checked
- Formal Review: APPROVED by @user (or "not required by repo policy")
```

**Forbidden pattern**: `### PR #N — ✅ MERGED YYYY-MM-DD` alone (no condition evidence)

**For post-hoc verifiability**: the ralph improve 5-A2 step and the workflow.md supervision checklist Step 7 read this information for verification. Without evidence, `✅`-only entries are classified as "merged without checking conditions" suspects during supervision.

## Merge-recommendation AskUserQuestion format (CRITICAL — HARD STOP)

**When recommending PR merge via AskUserQuestion, every option's description must include evidence for the five conditions.**

```typescript
{
  label: "PR #N squash merge",
  description: "CI: 4/4 ✅ | AI Review: CodeRabbit ✅ Copilot ✅ | Test Plan: 5/5 ✅ | Formal Review: APPROVED (or 'not required by repo policy')"
}
```

**Forbidden patterns (insufficient description)**:
- `"merge conditions satisfied"` (which conditions are unclear)
- `"CI passed"` (Test Plan, AI Review missing)
- A label with no description

**Verification procedure (HARD STOP)**:

Right before authoring the merge-recommendation AskUserQuestion, verify all five conditions:

```bash
# 1. CI status
gh pr checks <N> --json bucket -q '[.[] | .bucket] | group_by(.) | map({(.[0]): length}) | add'

# 2. AI Review Summary — count of 🔴 Critical (forbid merge if ≥ 1)
gh api repos/{owner}/{repo}/issues/<N>/comments \
  --jq '.[] | select(.body | startswith("## AI Review Summary")) | .body' \
  | grep -c '🔴 Critical' && echo "BLOCKED: Critical unresolved"

# 2b. AI Review actionable status
gh pr view <N> --json comments -q '.comments[] | select(.body | contains("actionable")) | .body' | head

# 3. Unchecked Test Plan items
gh pr view <N> --json body -q '.body' | node scripts/check-test-plan.js || echo "BLOCKED: Test Plan unchecked"

# 4. Formal Review (per repo policy)
gh pr view <N> --json reviews -q '[.reviews[] | select(.state == "APPROVED") | .author.login]'
```

**Any one of the four unsatisfied = the AskUserQuestion options must NOT include "merge"**. Offer "address <missing condition> then merge" instead.
