# Post AI Review Summary + Formal Review + Status + Deferred registration

Post AI Review Summary (as issue comment or unified into Formal Review body) + emit Status line + immediately register Deferred Actionable items. The core posting stage of the consolidate workflow.

Entry: `Skill("consolidate", "post ...")` or `pr.md` Workflow Step 7 / Step 7.5 / Step 7.6.

## Step 7: Post AI Review Summary + Formal Review

**Draft-PR gate (HARD STOP — re-check even on direct entry)**: `pr.md` Workflow Step 2 condition 4/5 skip draft and non-default-base-staging PRs before ever reaching this step — but `post.md` can also be entered directly (`Skill("consolidate", "post ...")`), bypassing that check. Before posting, re-verify: `gh pr view <NUMBER> --json isDraft --jq '.isDraft'`. If `true`, **stop — do not post**, and report the draft state instead. A Summary documenting the absence of review ("no findings", "no review needed for staging") is not an exception; it is the exact violation this gate exists to prevent.

**Always post a summary** (unless user chose "Skip" in Step 5, or the draft gate above fired).
The summary MUST include a detailed table of the findings, verification notes, and status.

### Interactive gate (when `--interactive` is on — literal or auto-activated by args)

Before the Summary POST in 7-A / 7-B below, the caller MUST follow the **Interactive flow contract** defined in `SKILL.md`:

1. Write the Summary body to `.tmp/summary-draft.md` (do not POST yet)
2. Emit a chat summary (Source matrix line + finding counts per Severity + verdict line + draft path)
3. Call `AskUserQuestion` with options: `Approve as-is` / `Edit (specify in Other)` / `Reject — do not POST`
4. Apply user edits → re-present → re-ask, until Approve or Reject
5. On Approve, proceed to 7-A or 7-B per the medium decision table below. On Reject, skip the POST and record the reason in chat (Step 7.5 status line still emitted).

If `--interactive` is off, proceed directly to medium decision + POST (deterministic flow). The Interactive gate applies even when "Summary is procedure (automatic)" is otherwise asserted — automation applies to whether-to-post (Axis A is procedural), not to body content review (which is a separate axis requested via `--interactive`).

### Summary comment title template (MANDATORY)

```markdown
## AI Review Summary — [receiving-code-review](https://skills.sh/obra/superpowers/receiving-code-review)
```

Plain `## AI Review Summary` is forbidden. The link form above is required.

**Caller retitle does NOT touch this Summary title (HARD STOP)**: a caller "rename the review → X" instruction scopes to the **Code Review comment** (Step 3.5.3 / `internal.md` "Caller-supplied custom title contract") — NEVER this Summary. The Summary heading stays `## AI Review Summary — [receiving-code-review](...)`. The two comments must not share the "Summary" token: the Code Review comment's heading must contain **no** "Summary" (e.g. `## Code Review — [requesting-code-review](...)`), this Summary comment owns "Summary" exclusively.

### Update Promotion PR Body with Cumulative Commits (HARD STOP)

When consolidating a promotion PR (e.g., `next-fix` or `next-feat` -> `main`), if new commits have been merged into the promotion branch since the PR was created, the PR body (description) must be updated to keep the curated list of commits and files in sync.

1. Enumerate all commits on the branch that are not yet on the base branch (e.g., `git log origin/main..origin/next-fix --oneline`).
2. Edit the PR body via `gh pr edit <NUMBER> --body-file <file>` with the updated commit list and affected files.

### Pre-Summary gate — Code Review comment MUST already exist (HARD STOP — visible even if internal.md was skipped)

**Before posting this Summary, a Code Review comment (Step 3.5.3, `requesting-code-review` link — under whatever title, default `## Internal Code Review` or a caller custom title like `## Code Review`) MUST already exist on the PR.** This gate is restated here in post.md (not only in internal.md) so that skipping the internal.md topic does not also skip the 2-comment invariant.

```bash
gh api repos/{owner}/{repo}/issues/{N}/comments \
  --jq '[.[] | select(.body | test("requesting-code-review"))] | length'
```

- Result `0` → **STOP. Do not post the Summary.** Return to Step 3.5 (internal.md) and post the Code Review comment first. Posting the Summary alone (or merging both into one comment) is the documented 6-recurrence violation ("Review comment ≠ AI Review Summary").
- Result `≥1` → the paired Code Review comment exists; proceed with the Summary post (chronologically after it).

### Step 3.5.3 review comment ↔ Step 7 Summary paired pattern

- Step 3.5.3 = Internal Code Review (`internal.md` `### Post/update review comment` section: `## Internal Code Review — [requesting-code-review](...)`) — code-reviewer subagent findings
- Step 7 = AI Review Summary — overall reviewer aggregation + conclusion (use template above)

The two comments' superpowers links form a pair (requesting ↔ receiving). When one is updated, verify the other for consistency. **Do not merge them into one or post only one** (omitting Step 3.5.3 = procedure incomplete).

#### Chronological order requirement (HARD STOP)

**The Internal Code Review comment must appear chronologically BEFORE the AI Review Summary comment on the PR timeline** — Step 3.5 precedes Step 7 in the workflow, and that ordering must be visible to anyone scrolling the PR. Reviewers reading the PR scroll top-to-bottom; the Summary is the conclusion and belongs last.

| # | Don't | Do |
|---|-------|-----|
| 1 | Post AI Review Summary as a new comment when an Internal Review is still pending — Summary lands above the later Internal Review | Post Internal Code Review first (Step 3.5.3) → only then post the Summary (Step 7) so Summary is chronologically last |
| 2 | After an ad-hoc consolidate bypass that posted Summary first, simply append the Internal Review as a new comment — leaves the paired comments in reversed order | When re-executing consolidate properly, detect the order error and swap contents (see "Order-correction damage control" below) |
| 3 | Treat the pairing as order-agnostic ("both exist, that's enough") | Order is visible signal: Summary at the bottom = "final consolidated verdict". Summary above Internal Review = confusing |

#### Order-correction damage control — Summary posted before Internal Review (HARD STOP)

**When the AI Review Summary was posted before the Internal Code Review (e.g., during an ad-hoc bypass or a prior consolidate run that completed Step 7 without Step 3.5), do NOT create a third comment to "rebalance".** Swap the contents of the two existing comments by PATCH so the older comment carries the Internal Code Review and the newer comment carries the AI Review Summary.

Procedure:

1. Identify both comments by ID:
   ```bash
   # Older comment (currently AI Review Summary, posted by mistake first)
   gh api repos/{owner}/{repo}/issues/{N}/comments --jq '.[] | select(.body | startswith("# 🤖 AI Review Summary") or startswith("## AI Review Summary")) | .id'

   # Newer comment (currently Internal Code Review, posted after — too late)
   gh api repos/{owner}/{repo}/issues/{N}/comments --jq '.[] | select(.body | startswith("## Internal Code Review")) | .id'
   ```
2. **PATCH the older comment** with the Internal Code Review body (full body, prescribed `## Internal Code Review — [requesting-code-review](...)` title)
3. **PATCH the newer comment** with the AI Review Summary body (full body, prescribed `## AI Review Summary — [receiving-code-review](...)` title)
4. Verify the chronological order on the PR page

| # | Don't | Do |
|---|-------|-----|
| 1 | Add a third comment containing the AI Review Summary "to put a Summary at the bottom" — pollutes the PR timeline with duplicated Summary content | PATCH the two existing comments to swap content. No new comment |
| 2 | Delete the older Summary comment and re-post — destroys the comment-ID URL anyone already referenced | PATCH preserves the URL; only the content changes |
| 3 | Use `minimizeComment` (OUTDATED) on the older Summary as a workaround | Minimize hides the content but does not move it. The order error persists; the swap is the only correct fix |
| 4 | Update only one of the two comments and leave the other contradicting | Swap is atomic: PATCH both in the same pass so the paired-content invariant holds |

Why PATCH-swap (and not delete + repost): PATCH preserves the comment ID and URL — anyone who linked to either comment (commit message, issue thread, chat) still resolves to a valid comment, just with corrected content. Deletion + repost breaks every existing link.

Self-check (before posting a new Step 7 Summary comment):

1. Does an AI Review Summary already exist on this PR? — `gh api .../comments | jq '.[] | select(.body | startswith("# 🤖 AI Review Summary") or startswith("## AI Review Summary"))'`
2. If yes, does an Internal Code Review also already exist? — same query for `## Internal Code Review`
3. If both exist and the Summary's `created_at` precedes the Internal Review's `created_at` → **order is reversed**. Apply the PATCH-swap damage control. Do not create a third comment

### Medium selection — Mergeable + Formal Review action → unified POST (HARD STOP — 2026-05-22 reinforcement)

The Summary body and the Formal Review body carry the **same verdict information** for Mergeable PRs. Posting them as separate media (issue comment + Formal Review) duplicates content. **When all of the following hold, Summary is posted as the Formal Review body (single POST). Issue comment Summary is forbidden:**

1. PR `mergeable: MERGEABLE` (from `gh pr view --json mergeable`)
2. Current user is a requested reviewer (`reviewRequests` includes current account)
3. Step 5 Axis B answer = `APPROVE` / `COMMENT` / `REQUEST_CHANGES` (not `Skip formal review`)

> **Precondition (HARD STOP — 2026-05-26)**: When the current user is a requested reviewer, **this medium table must NOT be consulted until the Step 5 Axis B ask has been answered** (see `decide.md` "Axis B ask precedes Summary medium decision/posting"). The `Non-Mergeable → issue comment only, Formal Review skipped` row is an auto-skip that applies **only after** the Axis B ask — it does not authorize posting an issue comment Summary before asking. For a requested reviewer, `mergeable: CONFLICTING` does NOT permit auto-posting the Summary; ask Axis B first, then the answer (incl. `Skip`) decides the medium.

| PR state | Medium | Posting |
|----------|--------|---------|
| **Mergeable + Formal Review action (APPROVE/COMMENT/REQUEST_CHANGES)** | **Unified** | Summary body → Formal Review POST only. **No issue comment Summary** |
| Mergeable + Skip formal review | Issue comment only | `gh pr comment` Summary only |
| Non-Mergeable (CONFLICTING/UNKNOWN) | Issue comment only | `gh pr comment` Summary only (Formal Review skipped — merge blocked anyway) |
| **Not a requested reviewer + author ≠ me** | **Unified (Formal Review POST)** | Summary body → Formal Review POST. Event auto-decided per "Non-requested reviewer event policy" below. **No issue comment Summary** when Formal Review is posted |
| Not a requested reviewer + author == me (self-authored PR) | Issue comment only | `gh pr comment` Summary only — self-approving own PR via Formal Review is non-conventional |

### Non-requested reviewer event policy (HARD STOP)

When the current user is **not a requested reviewer** but the **author ≠ me** (i.e., a peer reviewer scenario where review request was not formally issued), the Summary still POSTs as a **Formal Review**. Issue comment medium is forbidden — `reviews` array is the canonical record, and a peer Review without a request still belongs there.

**Event auto-decision** (caller-decided, no ask in the auto cases):

| Condition | Event | Caller action |
|-----------|-------|---------------|
| Critical findings exist (after Step 4 classification) | `REQUEST_CHANGES` | Auto-POST (no ask) — Critical = merge blocker, peer review's duty is to surface it |
| Non-Mergeable (CONFLICTING/UNKNOWN) OR CI failing OR Test Plan unchecked items > 0 | `COMMENT` | Auto-POST (no ask) — APPROVE is technically impossible while merge gates are open; COMMENT records the review without a merge-enabling verdict |
| Critical = 0 AND Mergeable AND CI pass AND Test Plan all checked (or N/A) | **APPROVE candidate → ask** | `AskUserQuestion` (question text MUST identify the PR: `PR #<N> (<owner>/<repo>)` + URL): `APPROVE` / `COMMENT only` / `Skip Formal Review (issue comment fallback)` — Important/Minor findings do NOT block the APPROVE candidate (Important = "Should fix, does not block merge" per Severity definition) |

**Why event auto-decide for non-APPROVE cases**: a peer reviewer's "what verdict to issue" decision is determined by the codebase state, not by user preference. Critical present = REQUEST_CHANGES is the only correct verdict; APPROVE under Critical = lying to GitHub merge gates. Conversely, "would APPROVE but Mergeable/CI/Test Plan blocks it" = COMMENT (record the review without falsely enabling merge). Only the APPROVE-candidate case is a user decision (the user may reserve APPROVE judgment).

| # | Don't | Do |
|---|-------|-----|
| 1 | Post Summary as issue comment because "I'm not a requested reviewer" | If author ≠ me, Formal Review POST is mandatory. Issue comment medium reserved for self-authored PRs |
| 2 | Ask the user "Formal Review or issue comment?" for non-requested reviewer | Medium is deterministic by the table above — Formal Review POST when author ≠ me, period |
| 3 | Auto-APPROVE when Critical = 0 + Mergeable + CI pass | APPROVE is a user decision even in the auto-eligible case. Caller asks; user answers |
| 4 | Issue COMMENT event when Critical > 0 ("less confrontational") | Critical > 0 = REQUEST_CHANGES is the only honest verdict. Auto-POST REQUEST_CHANGES — do not soften to COMMENT |
| 5 | Skip Formal Review POST when APPROVE candidate ask is rejected/skipped | If user picks "Skip Formal Review", fall back to issue comment Summary (Mergeable + Skip row in main table). Do not silently abort |

**Self-check (every time before Summary POST for author ≠ me PR)**:

1. Did Step 4 classification produce a Critical count? Used as the primary branch
2. Are Mergeable / CI / Test Plan gates all green? Used as the APPROVE-candidate qualifier
3. If REQUEST_CHANGES or COMMENT is auto, did you emit a chat note explaining why no ask? (e.g., "Critical 1 → REQUEST_CHANGES auto; no ask")
4. If APPROVE candidate, did you call `AskUserQuestion` with 3 options (APPROVE / COMMENT only / Skip)?
5. Did you avoid asking "Formal Review or issue comment?" — medium itself is deterministic, only the event for APPROVE candidate is asked

### Posted comments on an author ≠ me PR are immutable records (HARD STOP)

Once the Internal Code Review / AI Review Summary comment has been posted on a PR you did **not** author, treat it as an **immutable record** — do NOT `minimizeComment`/resolve it to "tidy up" after the author acts on the findings. Over-minimizing an already-posted peer review erases the review trail that the PR audit relies on. When findings are addressed or deferred, close them out by updating the tracking medium (`fix_plan.md`) only; leave the posted comment visible.

### Authorship-aware merge recommendation in Summary body (peer reviewer disclaimer)

When Summary body includes a `Merge Recommendation` line AND author ≠ me, append a one-line disclaimer that the recommendation is advisory:

```markdown
**Merge Recommendation**: <strategy>
**Reason**: <reason>
> Note: above is reviewer's advisory opinion. Final merge strategy/timing is at the author's discretion.
```

Localize the disclaimer to the repo's default language (Korean for PRIVATE Korean-default repos per opensource.md, English for PUBLIC). Omit the disclaimer when author == me (self-authored PRs — your own merge strategy is yours).

| # | Don't | Do |
|---|-------|-----|
| 1 | Post Summary as issue comment AND as Formal Review separately when Mergeable + APPROVE | Single Formal Review POST with Summary body. Skip issue comment |
| 2 | Use a short Formal Review body ("Internal Code Review complete...") + link to issue comment Summary | Embed the full Summary table (CodeRabbit/Copilot/Internal Review breakdown + verdict) directly in the Formal Review body |
| 3 | Treat Step 7-A as "always required" regardless of PR state | Step 7-A applies only when Formal Review is skipped or PR is Non-Mergeable |
| 4 | Post Summary issue comment first → then Formal Review with the same content | Decide medium first based on Mergeable + Axis B → POST once in the correct medium |

#### Self-check (every time before Step 7 POST)

1. `gh pr view <N> --json mergeable` → MERGEABLE?
2. Current user in `reviewRequests`?
3. Step 5 Axis B = APPROVE/COMMENT/REQUEST_CHANGES (not Skip)?
4. All 3 yes → **Unified POST** (go to 7-B with Summary body). Skip 7-A
5. Any no → **Separate**. Post 7-A issue comment; conditionally POST 7-B if Axis B = APPROVE/COMMENT/REQUEST_CHANGES

#### Damage control — Summary already posted in wrong medium (HARD STOP — 2026-05-26)

**If the AI Review Summary was already posted as an issue comment (e.g., medium auto-decided before the Axis B ask) and a Formal Review action is then chosen, do NOT create additional garbage.** Reuse the existing issue comment Summary as the review content and submit the Formal Review with an **empty body** (`gh pr review <N> --approve` / `--comment` / `--request-changes` with no `--body`).

| # | Don't | Do |
|---|-------|-----|
| 1 | Embed the full Summary into a new Formal Review body (duplicating the already-posted issue comment) | `gh pr review <N> --approve` with **no body** — the existing issue comment Summary is the review content |
| 2 | Add another issue comment ("Update" / "Formal Review note") | No new comment. Empty-body Formal Review only |
| 3 | Delete the already-posted issue comment Summary then re-post in the "correct" medium | Leaving it is cleaner than churning. Deleting + re-posting = more noise than an empty-body approve |
| 4 | Dismiss a duplicate empty review to "clean up" | An empty-body review has no content; dismissing adds a dismiss-trail = more garbage. Leave benign duplicates |

**Why empty body**: Formal Review is PATCH-impossible and the issue comment Summary already carries the verdict. A bodied Formal Review would duplicate that content. The empty-body review only supplies the missing review **state** (APPROVED/etc.) without content duplication. This is the recovery path when the Axis B-ask-first gate (see `decide.md`) was missed.

**User instruction precedent (2026-05-26)**: the user directed that when the medium was already mis-posted, do not create more garbage with an additional message — submit an empty-body approve instead. The recovery is an empty-body approve, not a new bodied review/comment.

### Merge recommendation preconditions (Mandatory check — run before drafting Summary)

```bash
# Check the number of unchecked Test Plan items (mandatory before drafting Summary)
gh pr view NUMBER --json body --jq '.body' | grep -c '\- \[ \]' || true
```

**If the result of the command above is non-zero, "Ready to merge" notation is strictly forbidden.** Instead, mark as `Test plan N items unverified — Playwright verification required`.

Full conditions:
1. All AI review actionable items addressed
2. **PR body Test plan `- [ ]` unchecked items = 0** — verify via the command above. Even one unchecked item forbids "Ready to merge"
3. **All user-reported issues fixed** — verify that issues mentioned in the `/consolidate` arguments have been resolved

**Resolving deployment-required verification items**: If the Test Plan has "post-deployment verification" items, pre-verify on a legacy/staging environment using the feature branch image. Since this is verifiable without master merge, do not record "post-deployment verification required" as a merge-blocking reason.

When unmet, write `Actionable Items PENDING fix.` in the Summary + state the unmet conditions. **Do not ask "shall we merge?"**

If all conditions met, evaluate the PR's commit history (`gh pr view NUMBER --commits`) **AND the PR's stated intent (description/body, checklist referenced)** to recommend a merge strategy:

#### PR intent verification first (HARD STOP — before commit analysis)

| Stated intent in PR description / checklist | Merge strategy |
|--------------------------------|---------|
| **"post-hoc review"**, **"history preservation"**, **"post-hoc integration of master direct pushes"**, **"integration of unreviewed commits"** | **Merge commit enforced** — preserving atomic commits is the PR's purpose itself. Squash forbidden |
| "Core PR is feature implementation + review" | Branch by commit characteristics (see below) |

| Commit characteristics (when PR purpose is unstated) | Merge strategy |
|----------------------------------------|---------|
| Messy WIP commits, automated agent loop commits, multiple minor fixes ("fix typo") representing a single logical feature | Squash and merge |
| Carefully curated, atomic commits (e.g., separated by `commit-tidy`) with independent value | Create a merge commit |

| # | Don't | Do |
|---|-------|-----|
| 1 | Recommend squash based only on commit count/size/messages without checking PR description "Why" / checklist references | Read the PR description "Why" section + checklist references first → if intent is post-hoc review / history preservation, always merge commit |
| 2 | Justify squash on discovering cherry-pick commits as "duplicates of originals" | Cherry-pick itself may be the PR's purpose (post-hoc review). Decide after checking PR description |
| 3 | Force a single "Squash (Recommended)" option | If atomic value / user intent is ambiguous, provide both options + trade-off descriptions |
| 4 | Lay out 6+ justification points in the answer | Cite 1st-source (PR description) in one line + matrix branching only. Justify only when user asks |

**Self-check (every time before recommending merge strategy)**:

1. Did you Read the PR description's "Why" or checklist references? (Skipping description = violation)
2. Does the description contain keywords like "post-hoc review", "history preservation", "direct-push integration", "unreviewed commits"? → If yes, always merge commit
3. Are there cherry-pick commits? → If originals exist atomically on master or another branch, squashing diverges the same change into a different SHA → prefer merge commit

### Summary body example

```markdown
## AI Review Summary — [receiving-code-review](https://skills.sh/obra/superpowers/receiving-code-review)

| # | Source | Severity | Finding | Status |
|---|--------|----------|---------|--------|
| 1 | `copilot` | 📝 Minor | 🛠️ Missing error handling — handled in existing middleware | ⚪ Rejected |
| 2 | `coderabbitai` | 🟡 Important | ⚠️ N+1 query vulnerability — verified via grep | 🔴 Fixed (commit abc123) |
| 3 | Internal Code Review | 📝 Minor | 📝 Unused import | 🟡 Minor |
| 4 | @reviewer-login | 🟡 Important | 🛠️ DB findUnique lacks try/catch — diverges from sibling route | 🔴 Pending |

[✅ All AI reviews passed. Ready to merge.

**Merge Recommendation**: [Squash and merge / Create a merge commit]
**Reason**: [e.g. Contains multiple WIP/agent loop commits / Contains carefully split semantic commits]

/ ⏳ Actionable Items PENDING fix.]
```

### Status column value spec — fix_plan tracking tags forbidden (HARD STOP)

**The Findings table `Status` column must only carry values a GitHub PR comment reader can interpret immediately as the "current handling state".** Carrying over fix_plan.md's internal tracking tags (`[REVIEW_FEEDBACK]`, `[BLOCKED]`, `[DEFERRED]`, `[REJECTED]`, `[RALPH_TODO]`, etc.) verbatim is a **medium-separation violation** — fix_plan is an internal tracking index; a GitHub PR comment is an external reader-facing medium.

**Allowed Status values** (aligned with the Summary body example):

| Value | Meaning |
|-------|---------|
| `🔴 Fixed (commit <sha>)` | Fix applied in this PR or a follow-up commit — SHA citation mandatory (cross-link) |
| `🔴 Pending` | Immediate fix required (typically Critical) — awaiting author/reviewer action |
| `🟡 Deferred (author follow-up)` | Follow-up handling (separate PR/issue/post-merge backport etc.) — plain phrasing |
| `🟢 Deferred (no action)` | Review concluded irrelevant/unnecessary — plain phrasing |
| `⚪ Rejected — <one-line reason>` | Rejected + reason inline |
| `🟢 Verified — <evidence>` | Verification passed + evidence (curl/test/grep result inline) |

**The fix_plan tracking tags are for Step 7.6 deferred registration only (when writing entries inside fix_plan.md's Hold section)**. Carrying the same tag into the Summary body Status column leaves the GitHub reader with no meaning (zero readability).

| # | Don't | Do |
|---|-------|-----|
| 1 | `\| Status \| ... \| [REVIEW_FEEDBACK] \|` — using a fix_plan tracking tag in the Summary Status column | `🟡 Deferred (author follow-up)` or `🔴 Pending` etc. — semantic value |
| 2 | `\| Status \| [DEFERRED] \|` / `\| Status \| [BLOCKED] \|` — bracket-prefix tracking pattern | The bracket form itself is a fix_plan index signal. Summary uses emoji + plain phrasing |
| 3 | "Same tag is convenient since it's registered in fix_plan anyway" reasoning | fix_plan deferred entry (Step 7.6) ≠ Summary Status (Step 7). Different medium → separate notation |
| 4 | Mirroring the same tag in both Summary and fix_plan as a cross-link attempt | Cross-link by citing the fix_plan section URL / entry from the Summary body (when needed). Do not mirror the tag |
| 5 | Realizing only after the user points out the readability issue that a fix_plan tag like "[REVIEW_FEEDBACK]" appeared in the response | Run the self-check below every time before drafting the Summary |

**Self-check (every time before POSTing the Summary)**:

1. Grep every cell in the Findings table Status column: `[REVIEW_FEEDBACK]|[BLOCKED]|[DEFERRED]|[REJECTED]|[RALPH_TODO]` — any single match is a violation
2. On match, replace with the mapping from the "Allowed Status values" table above:
   - `[REVIEW_FEEDBACK]` → `🟡 Deferred (author follow-up)` or `🔴 Pending` (depending on severity)
   - `[BLOCKED]` → `🔴 Pending — <blocker reason>` or `🟡 Deferred — <reason>`
   - `[DEFERRED]` → `🟢 Deferred (no action)` or `🟡 Deferred (author follow-up)`
3. Re-grep after replacement — confirm zero matches before POST

### Conclusion line emoji rule (HARD STOP)

| Conclusion state | Emoji | Forbidden |
|----------|--------|------|
| Critical 0 + Ready to merge | ✅ | 🔴 (red is a "problem present" visual signal — attaching it for 0 count causes confusion) |
| Actionable PENDING / Incomplete Test Plan | ⏳ | 🔴 (PENDING ≠ Critical) |
| Critical unresolved | 🔴 | ✅ (looks like no problem) |

### Status ↔ Merge-Recommendation consistency (HARD STOP)

**The per-finding Status column and the conclusion / Merge Recommendation must agree — derive the conclusion FROM the Status column, never write the two independently.** Status encodes blocking: `🔴 Pending` = blocks merge (fix first), `🟡/🟢 Deferred` = non-blocking (post-merge follow-up / no action). A finding cannot be both `Deferred` and the reason the merge is held.

- Any finding `🔴 Pending` → conclusion ⏳ "Actionable Items PENDING / Not ready to merge", Merge Recommendation "Hold — address the Pending findings first".
- Zero `🔴 Pending` (all Deferred / Rejected / Verified) → ✅ "Ready to merge"; if the Test Plan is unchecked, "Ready pending Test Plan" — the hold reason is the Test Plan (Step 7.5), NOT the findings.

| # | Don't | Do |
|---|-------|-----|
| 1 | Mark all findings `🟡 Deferred` then conclude "Hold — address the Important findings first" | If the Important findings block merge, set their Status `🔴 Pending`. If genuinely deferred, the conclusion cannot cite them as the merge blocker |
| 2 | Write the Status column and the Merge Recommendation as independent fields | Derive the recommendation from the Status column: any `🔴 Pending` present = Hold; zero Pending = Ready |
| 3 | Use an unchecked Test Plan as grounds to re-label `Deferred` findings as blockers in prose | Test Plan incompleteness blocks "Ready to merge" on its own — keep findings at their true Status, cite the Test Plan as the hold reason |

**Self-check (before POSTing the Summary — consistency)**:

1. Conclusion says "Hold" / "Not ready to merge" / cites findings to address first? → every finding it names as a blocker must be `🔴 Pending`, not `Deferred` or `Fixed`.
2. All findings `Fixed` / `Deferred` / `Rejected` / `Verified` (zero `🔴 Pending`)? → conclusion must be ✅ "Ready to merge" (or "Ready pending Test Plan" with a `⏳` emoji when the Test Plan is unchecked), never "Hold to address the findings".
3. Read the Status column and the Merge Recommendation together — is any finding both `Deferred`/`Fixed` and the cited reason the merge is held? That is the contradiction; reconcile before POST.

Only include reviewers that actually posted reviews on this PR, and only include non-trivial findings (skip 'No actionable comments' rows if there are other findings, or state 'No actionable findings' in the table if all reviewers are clean).

### Source attribution column is MANDATORY (HARD STOP)

**The findings table MUST include a `Source` (or `Reviewer`) column attributing every row to the exact reviewer login it came from** — coderabbitai, copilot, @human-login (e.g., @reviewer-login), Internal Code Review, etc. Composing a findings table with only `# | Severity | Type | Location | Summary` columns strips the audit trail and conflates findings from multiple reviewers into an anonymous pool.

**Source cell formatting**: write @mentions, SHAs, and URLs **bare** — never wrap them in backticks. GitHub renders bare `@username` as an autolinked mention (notification fires), and a backticked `` `@username` `` becomes inline code with no autolink. The same applies to commit SHAs and **real** PR/issue references in any Summary field, not just the Source column. This rule lives in the global rules file `git.md` under the autolink HARD STOP section; consolidate-posted bodies must comply.

**Finding/item-number references — the inverse direction (HARD STOP)**: bare `#N` is autolink-correct **only for a real PR/issue reference**. A finding **item number** — a reference to a row of the findings table or to a reviewer's numbered comment, e.g. a narrative line like `Notable: #2 and #3 sit inside the CI workflows` — is NOT a PR/issue reference. Written bare, GitHub autolinks it to the unrelated PR/issue of that number **in the same repo**, creating a permanent false timeline backref that comment editing cannot remove. Wrap every finding/item number in backticks (`` `#2` ``, `` `#14/#15` ``) or reword to a non-`#` form (`finding 2`, `row 2`). This applies everywhere in the Summary body — the findings table cells, the `Notable`/conclusion narrative, and any inline prose — not just the Source column. Direction summary: **real PR/issue/SHA/@mention → bare (autolink ON); finding/item number → backtick (autolink OFF)**.

| # | Don't | Do |
|---|-------|-----|
| 1 | Findings table columns: `# | Severity | Type | Location | Summary` (no source) | Add a `Source` column: `# | Source | Severity | Type | Location | Summary`. Every row's `Source` cell names the exact reviewer login (or `Internal Code Review`) the finding originated from |
| 2 | Collapse multiple distinct human MEMBER reviewers into a single "Internal Code Review" entry | Each human reviewer login is a separate `Source` value. Internal Code Review is the subagent-generated review only; human collaborator reviews carry the reviewer's GitHub login |
| 3 | Omit the header reviewer matrix line when one of the sources is a non-bot MEMBER review | The opening `> Reviewer matrix:` line enumerates every source enumerated in `collect.md` Step 3 — bots + human MEMBER/OWNER reviews. Missing any source there = missing it in the table too |
| 4 | Merge two findings from different sources into one row "to deduplicate" | Keep one row per (source × finding). If two reviewers raised the same finding, write two rows with the same `Location` + `Summary` but distinct `Source`. Deduplication belongs in the chat narrative, not in the table |
| 5 | Wrap @mentions / SHAs / URLs in backticks in the Source cell or anywhere in the Summary body (e.g., `` `@octocat` ``, `` `de59590` ``, `` `https://...` ``) | Write them bare so GitHub autolinks fire: `@octocat`, `de59590`, `https://github.com/...`. Bot logins (coderabbitai, copilot) are bot identifiers, not human mentions — write them bare without the `@` prefix |
| 6 | Append role/qualifier parentheses to the Source cell (e.g., `@octocat (MEMBER review)`, `@octocat (OWNER)`) | The `@id` already identifies the reviewer — no role qualifier needed. Source cell carries only the bare identifier: `@octocat`, `coderabbitai`, `Internal Code Review` |
| 7 | Reference a finding by bare `#N` in the `Notable`/conclusion narrative or any cell (e.g., `Notable: #2 and #3`, `#14/#15 correctly flag ...`) — autolinks to the unrelated PR/issue #N in the repo (permanent false backref) | Backtick every finding/item number: `` `#2` ``, `` `#14/#15` ``, or reword to `finding 2` / `row 2`. Only a **real** PR/issue reference stays bare |

**Self-check (every time before POSTing the Summary)**:

1. Did `collect.md` Step 3 enumerate every reviewer (bot + human MEMBER/OWNER/COLLABORATOR)? Re-run the query if uncertain
2. Does the Summary's `> Reviewer matrix:` opening line list every enumerated source by name?
3. Does the findings table have a `Source` column?
4. Is every row's `Source` cell populated with the exact reviewer login (not blank, not "AI", not "external")?
5. If a finding was raised by two reviewers independently, are both rows present?
6. Scan the entire body — does any `@username`, 7+ hex SHA, or full URL sit inside backticks? If yes, unwrap to bare so GitHub autolink fires (per the `git.md` autolink rule)
7. Scan the entire body for bare `#[0-9]+` (grep `#[0-9]` sitting outside backticks — the `Notable`/conclusion narrative is the usual offender). For each match decide: **real** PR/issue reference (keep bare, autolink desired) or finding/item number (wrap in backticks / reword — autolink must be suppressed)? A bare finding number silently autolinks to the wrong PR/issue in the repo

## 7-A. Issue comment Summary (when unified POST does NOT apply)

Conditions to use 7-A: Non-Mergeable / Skip formal review / Not a requested reviewer. Otherwise use 7-B unified POST.

```bash
# Check whether current user is a reviewer
gh pr view NUMBER -R owner/repo --json reviewRequests --jq '.reviewRequests[].login'
```

| Condition | Posting method | API |
|------|----------|-----|
| **Current user is a reviewer** | Formal PR Review (`event` specified) — see 7-B | `gh api repos/{owner}/{repo}/pulls/{number}/reviews` |
| **Not a reviewer** | Issue comment | `gh pr comment NUMBER --body-file ...` |

### Default posting (first post, 7-A)

```bash
# When not a reviewer — Comment
Write "/tmp/pr-review-summary.md" with summary content
gh pr comment NUMBER -R owner/repo --body-file /tmp/pr-review-summary.md
```

### Single Summary preservation guard (HARD STOP)

**Only one AI Review Summary comment must exist per PR.** When updates are needed, **PATCH (edit) the existing comment body instead of adding a new comment**.

#### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | After a major fix, add a new "Update" comment via `gh pr comment` | Find existing Summary comment ID and `gh api .../comments/{id} -X PATCH -f body=@file` |
| 2 | Accumulate new comments by just adding "Update N" prefix | Adding "Update 2" prefix in the body is OK, but **update the same comment via PATCH**. Creating new IDs is forbidden |
| 3 | Leave prior Summary as-is and post a new comment | (a) For a single comment, PATCH (b) For multiple stale Summaries, delete prior or `minimizeComment(OUTDATED)` |
| 4 | Think "edit history disappears so new comment is safer" | GitHub preserves edit history permanently (queryable via `?old_index=N`). Accumulating new comments = noise |
| 5 | Post Summary 2+ times in a single consolidate session | First post is a new comment; afterward fix → verify → on pass **PATCH the same comment**. Comment addition only once |
| 6 | A wrong comment exists and a different-kind comment is missing → roll back the wrong comment + POST a new comment for the missing one | **Reuse via swap PATCH**: PATCH the missing content into the wrong-comment slot, and PATCH the correct content into the other slot. New POST forbidden |
| 7 | Split processing into "rollback + new POST" | If an existing comment ID is PATCH-able, any content can be placed there. New POST = trash time-history accumulation |

#### Reuse mis-posted comments (swap PATCH preferred)

**When multiple comments are mis-posted, rearrange content via PATCH on existing comment IDs — not new POST.**

Example: comment A (Summary slot) was wrongly PATCHed + comment B (Internal Code Review) is missing.
- ❌ Don't: PATCH A back to the original Summary + POST a new comment C for Internal Code Review → C ends up at the chronological tail = trash record
- ✅ Do: PATCH A → Internal Code Review (chronological first = Step 3.5.3 slot) + PATCH B → Summary (chronological later = Step 7 slot)

**Principle**: Fill comment slots (chronological order) with existing PATCH-able IDs. Use new POST only when no PATCH-able slot exists.

#### PATCH procedure

```bash
# 1. Look up existing Summary comment ID
EXISTING_ID=$(gh api repos/{owner}/{repo}/issues/{N}/comments \
  --jq '[.[] | select(.body | contains("AI Review Summary")) | .id] | .[-1]')

# 2. Write new body (include Update prefix)
Write "/tmp/pr-review-summary.md" with updated summary content

# 3. Replace existing comment body via PATCH
gh api repos/{owner}/{repo}/issues/comments/${EXISTING_ID} \
  -X PATCH --input <(jq -n --rawfile body /tmp/pr-review-summary.md '{body: $body}')
```

#### Stale Summary cleanup (when already accumulated)

If the PR already has 2+ accumulated Summary comments:

1. **Keep the most recent one** — mark Update in the body + reflect latest state
2. **Remaining prior Summaries**:
   - Your own previously posted stale comment → `gh api repos/{owner}/{repo}/issues/comments/{id} -X DELETE` (own comments are deletable)
   - Prior comments by other people/bots → fold via `minimizeComment(OUTDATED)` GraphQL

```bash
# Delete own stale comment
gh api repos/{owner}/{repo}/issues/comments/{id} -X DELETE

# Or minimize via GraphQL (regardless of author)
gh api graphql -f query='
  mutation($id: ID!) {
    minimizeComment(input: {subjectId: $id, classifier: OUTDATED}) {
      minimizedComment { isMinimized }
    }
  }' -F id={node_id}
```

#### First post vs update branching

```bash
EXISTING_COUNT=$(gh api repos/{owner}/{repo}/issues/{N}/comments \
  --jq '[.[] | select(.body | contains("AI Review Summary"))] | length')

if [ "$EXISTING_COUNT" = "0" ]; then
  # First post — new comment
  gh pr comment N -R owner/repo --body-file /tmp/pr-review-summary.md
else
  # Update — PATCH the most recent comment
  EXISTING_ID=$(gh api repos/{owner}/{repo}/issues/{N}/comments \
    --jq '[.[] | select(.body | contains("AI Review Summary"))] | .[-1].id')
  gh api repos/{owner}/{repo}/issues/comments/${EXISTING_ID} \
    -X PATCH --input <(jq -n --rawfile body /tmp/pr-review-summary.md '{body: $body}')
fi
```

#### Self-check (every time before Summary posting — inspect both media)

**Issue comment medium** (PATCH-able):
1. `gh api .../issues/{N}/comments | jq '[.[] | select(.body | contains("AI Review Summary"))] | length'` → N items
2. N=0 → new comment (`gh pr comment`)
3. N≥1 → **PATCH** (`gh api .../comments/{id} -X PATCH`). Adding a new comment is forbidden
4. N≥2 (stale accumulation) → PATCH the most recent one + delete/minimize the rest

**Formal Review medium** (PATCH-impossible):
1. `gh api .../pulls/{N}/reviews | jq '[.[] | select(.user.login == "<self>") | select(.body | contains("AI Review Summary"))] | length'` → M items
2. M=0 → new POST possible (apply "Pre-check before Formal Review POST + post-publish verification" procedure above)
3. M≥1 → **new POST forbidden**. If update needed, either (a) dismiss existing review + new POST, or (b) switch to issue comment medium
4. M≥2 (duplicate accumulation) → keep the most recent + dismiss the rest (`gh api .../pulls/{N}/reviews/{review_id}/dismissals -X PUT -f message="..."`) or minimize

**Inspect both media in self-check (HARD STOP)** — Inspecting only one medium can leave duplicate accumulation in the other. Even with a PATCH-able Summary in issue comments, if a separate review accumulates in Formal Review, the GitHub UI displays 2 Summaries.

## 7-B. Formal Review submission

When **unified POST applies** (Mergeable + Formal Review action), this is the **only** POST — the Formal Review body contains the full Summary content.

When unified POST does **not** apply but Axis B = APPROVE/COMMENT/REQUEST_CHANGES (rare edge cases — e.g., PR became Non-Mergeable after Step 5 ask), 7-B is a **separate medium** from 7-A. Issue comment Summary does NOT satisfy GitHub's PR review request — the `reviews` array must contain an entry from the requested reviewer.

### Pre-check: existing review by current user (avoid duplicates)

```bash
GH_TOKEN="$(gh auth token --user <account>)" \
  gh api repos/<owner>/<repo>/pulls/<N>/reviews \
  --jq '.[] | select(.user.login == "<current-account>") | {id, state, submitted_at}'
```

- If existing review by current user → **skip Formal Review POST** (Formal Review is PATCH-impossible; resubmitting creates a duplicate that cannot be cleanly removed)
- If empty → proceed to POST

### POST procedure

**Unified POST body (Mergeable + Formal Review action)** — embed the full Summary in the Formal Review body:

```bash
# Write JSON payload — body = full AI Review Summary content
Write "/tmp/pr-formal-review.json" with:
{
  "event": "APPROVE",
  "body": "## AI Review Summary — [receiving-code-review](https://skills.sh/obra/superpowers/receiving-code-review)\n\n- **CodeRabbit**: walkthrough only (Free plan) — line-by-line review unavailable\n- **Internal Code Review** ([requesting-code-review](https://skills.sh/obra/superpowers/requesting-code-review)): Critical 0, Important 0, Minor N (deferred). Verification table + findings inline below.\n\n### Findings\n\n| # | Item | Type | Severity | Scope | Recommendation |\n|...|\n\n### Verdict\n\n🟢 **Critical 0, Important 0, Minor N (deferred OK). Merge OK.**"
}
```

**Separate POST body (unified does not apply)** — short verdict + link to issue comment Summary:

```bash
Write "/tmp/pr-formal-review.json" with:
{
  "event": "APPROVE",
  "body": "Internal Code Review complete. Critical 0, Minor N. Merge conditions met.\n\nDetails: https://github.com/<owner>/<repo>/pull/<N>#issuecomment-<id>"
}
```

**POST + verify**:

```bash
# POST
GH_TOKEN="$(gh auth token --user <account>)" \
  gh api repos/<owner>/<repo>/pulls/<N>/reviews \
  --method POST --input /tmp/pr-formal-review.json \
  --jq '{id, state, user: .user.login, url: .html_url, submitted_at}'

# 1st-source verification (HARD STOP — required after POST)
GH_TOKEN="$(gh auth token --user <account>)" \
  gh api repos/<owner>/<repo>/pulls/<N>/reviews \
  --jq '.[] | {id, user: .user.login, state}'
```

### Event mapping (from Step 5 Axis B answer)

| Axis B answer | `event` value | When to use |
|---------------|---------------|-------------|
| APPROVE | `APPROVE` | Findings clean, Critical 0, merge OK |
| REQUEST_CHANGES | `REQUEST_CHANGES` | Critical findings exist — block merge until fixed |
| COMMENT only | `COMMENT` | Review body only, no merge gating verdict |
| Skip formal review | (do not POST 7-B) | Issue comment Summary only |

### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | Post both 7-A issue comment and 7-B Formal Review with the same Summary content (Mergeable + APPROVE case) | Mergeable + Formal Review action → unified POST. Summary body goes directly into Formal Review. Skip 7-A |
| 2 | Treat AI Review Summary issue comment URL as evidence of APPROVE | Verify via `gh api .../reviews` — Formal Review lives in a different array than issue comments |
| 3 | Re-POST Formal Review when one already exists by current user | Pre-check via `gh api .../reviews`. Existing review = skip (Formal Review is PATCH-impossible) |
| 4 | Compose multi-line body inline with `gh api -f body=...` (PowerShell newline issue) | Write JSON file → `--input <file>` |
| 5 | Trust POST response without 1st-source verification | After POST, re-query `gh api .../reviews` to confirm `state` matches the intended `event` |
| 6 | Skip Formal Review POST because "findings are clean" (Mergeable case) | Clean findings + requested reviewer + Mergeable = APPROVE with Summary body inline. Mandatory POST |
| 7 | Use a short Formal Review body that links to a separate Summary issue comment in unified-POST case | Embed the full Summary table + verdict directly in the Formal Review body |

### Pre-check before Formal Review POST + post-publish verification (HARD STOP — prevent duplicate posting)

Formal Review is a **PATCH-impossible** medium. When multiple reviews accumulate on the same PR, cleanup is hard (the dismiss API exists, but a chronological trash record remains).

#### Pre-check (just before Formal Review POST)

```bash
# Check whether an AI Review Summary by current user already exists
EXISTING_REVIEW_ID=$(GH_TOKEN="$(gh auth token --user <account>)" \
  gh api repos/{owner}/{repo}/pulls/{N}/reviews \
  --jq '[.[] | select(.user.login == "<self>") | select(.body | contains("AI Review Summary"))] | .[-1].id // empty')

if [ -n "$EXISTING_REVIEW_ID" ]; then
  # Already posted → forbid new POST. dismiss + new POST, or switch to issue comment
  echo "WARN: Existing review $EXISTING_REVIEW_ID. POST forbidden. dismiss → new POST OR switch to issue comment"
fi
```

#### Post-publish verification (1st source — verify separately even if POST response parsing errored)

```bash
# After running the POST command, response parsing (python etc.) may fail with encoding errors (e.g., cp949 UnicodeEncodeError)
# → The API POST itself may have succeeded, so verify separately with 1st source
GH_TOKEN="$(gh auth token --user <account>)" \
  gh api repos/{owner}/{repo}/pulls/{N}/reviews \
  --jq '[.[] | select(.user.login == "<self>") | select(.body | contains("AI Review Summary"))] | length'
```

| # | Don't | Do |
|---|-------|-----|
| 1 | POST command output parsing fails (`exit 1`) → assume "total failure" and retry | Response parsing failure ≠ API failure. Verify posting status with 1st source (`gh api .../reviews`) before deciding to retry |
| 2 | POST same Summary → response encoding error → retry | Immediately after POST, query review count → if count≥1, forbid retry + clean up accumulated reviews |
| 3 | Skip existing review check before Formal Review POST | Pre-check step is mandatory (EXISTING_REVIEW_ID check above) |
| 4 | Think "Formal Review can be posted any time" | Formal Review is PATCH-impossible — accumulating POSTs creates chronological trash records. Only one first POST is allowed |

#### Self-check (every time before Formal Review POST)

1. Did Step 5 Axis B answer specify APPROVE / REQUEST_CHANGES / COMMENT? → If "Skip formal review" or not a requested reviewer, skip 7-B
2. **Unified POST conditions met?** (Mergeable + Formal Review action + requested reviewer) → If yes, body must contain the full Summary content (not a short verdict). Skip 7-A
3. **Does the Summary content contain merge-recommendation markers** (🟢 / "Merge OK" / "Ready to merge" / "Merge ready")? → If yes and current user is requested reviewer, 7-B Formal Review POST is **mandatory** — Skip not allowed (HARD STOP — see Step 5 conditional gate)
4. Did the pre-check confirm no existing review by current user? → If exists, skip POST
5. Did you write the body via JSON file (not inline `-f body=...`)?
6. Did you verify `state` via `gh api .../reviews` after POST?

## Optional Inline Review (line-specific annotation — when needed)

**Issue-level Summary is for the PR's overall evaluation. For recommendations targeting a specific line in a specific file, an inline review (line-level annotation) lets the author immediately see which line in the GitHub UI.** Inline is more effective than issue comments for residual recommendations not absorbed in the current PATCH cycle (deferred / post-Severity-downgrade).

> **Primary auto-fire path**: when line-specific findings exist, the Internal Code Review itself is posted as a single reviews API POST at Step 3.5.3 (`body` = full findings + `comments[]` = inline annotations) — policy (Critical+Important default / `--inline` = all; re-review = new POST every time) lives in `internal.md` "Medium decision" + "Inline auto-fire policy". This section provides the shared mechanics (payload, fields, verification) and covers the residual Step 7 case (deferred annotation after user decision).

### Triggers (recommended when all are met)

1. Step 4 classification has 1+ line-specific finding (file:line identifiable)
2. User decided not to fix immediately (deferred or Severity downgraded)
3. Already cited textually in the issue-level Summary, but author attention focus is needed

### gh CLI constraints

| Tool | Inline support |
|------|----------------|
| `gh pr review` CLI | ❌ Not supported (single review body only) |
| `gh pr comment` CLI | ❌ Issue comment (no line-level) |
| `gh api POST .../pulls/{N}/reviews` | ✅ `comments[]` array creates a line-level review (event = COMMENT / APPROVE / REQUEST_CHANGES) |
| `gh api POST .../pulls/{N}/comments` | ✅ Single line-level comment (outside a review) |

### Procedure (multi-file inline review)

```bash
# 1. Fetch PR head SHA
HEAD_SHA=$(GH_TOKEN="$(gh auth token --user <account>)" \
  gh pr view <N> -R <owner>/<repo> --json headRefOid --jq '.headRefOid')

# 2. Write JSON payload file (multi-line body MUST go through a JSON file)
Write "/tmp/pr-inline.json" with:
{
  "commit_id": "<HEAD_SHA>",
  "event": "COMMENT",
  "body": "Line-level opinion summary (overall review body — optional)",
  "comments": [
    {
      "path": "<file path included in diff>",
      "line": <line number>,
      "side": "RIGHT",
      "body": "<dual-label> — <problem> + <recommendation> + master commit/issue link"
    }
  ]
}

# 3. POST
gh api -X POST repos/<owner>/<repo>/pulls/<N>/reviews --input /tmp/pr-inline.json --jq '{id, html_url}'

# 4. Verify (confirm line-level comments were posted)
gh api repos/<owner>/<repo>/pulls/<N>/comments --jq '.[] | select(.pull_request_review_id == <review_id>) | {path, line, side, html_url}'
```

### Comment object fields

| Field | Meaning | Notes |
|-------|---------|-------|
| `path` | File path | Must be in PR diff (verify via `gh pr view --json files`) |
| `line` | Line number | `side: "RIGHT"` = after; `"LEFT"` = deleted line |
| `side` | `RIGHT` / `LEFT` | New / modified code is RIGHT |
| `start_line` + `start_side` + `line` + `side` | Multi-line comment | Optional |
| `body` | Comment body | dual-label + recommendation inline |

### Severity downgrade pattern (deferred Critical → Important inline)

When a Critical is decided as not-fixed-immediately, **downgrade Severity by one step** and post inline. The tone becomes "not an immediate merge blocker but a future extensibility recommendation". The Type category (⚠️ Potential etc.) stays the same.

| # | Don't | Do |
|---|-------|-----|
| 1 | Post Critical as-is inline after deferred decision | Downgrade Critical → Important + state the downgrade reason in the inline label (e.g., `🟡 Important — siteIndex hardcoded guard (Critical → Important downgrade)`) |
| 2 | Also change the Type axis (Potential → Refactor) | Change only the Severity axis. Keep the Type as-is (apply Step 4's dual-label orthogonal rule) |
| 3 | Autonomously downgrade without asking the user | Downgrade only when the Step 5 / Step 8 ask answer explicitly directs it or deferred is decided |

### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | Post every finding inline | Issue comment Summary is primary. Use inline only when line-specific + author attention is needed |
| 2 | Post inline without an issue comment Summary | Step 7 Summary is mandatory. Inline complements Summary (Summary = overall evaluation, inline = line-level annotation) |
| 3 | Try inline on a file not in PR diff | Verify path/line via `gh pr view <N> --json files`. Files outside diff return 422 unprocessable |
| 4 | Use `gh pr comment` to imitate inline (issue-level only) | Use `gh api POST .../pulls/{N}/reviews` + `comments[]` |
| 5 | Omit event and leave a pending review | Specify event (`COMMENT` / `APPROVE` / `REQUEST_CHANGES`). Pending requires a separate submit |
| 6 | Accumulate duplicate inline reviews on the same PR | Bundle multiple file:line comments into a single review POST. Additional lines = separate review POST |

### Self-check (every time before inline review POST)

1. Did you fetch the head SHA via `gh pr view <N> --json headRefOid`? (commit_id required)
2. Are all target paths present in `gh pr view <N> --json files` results?
3. Do line numbers match the file contents at PR head? (verify with `git show <head>:<path>`)
4. Does the body include the dual-label (Type | Severity)?
5. Is this item decided as not-fixed-immediately by the user? (For immediate fix, Step 6 Fix is preferred over inline)
6. Are Summary (Step 7) and inline consistent? (Summary marks as deferred + inline matches)

### Applied example (PR #352 page.tsx guard)

```jsonc
// /tmp/pr-inline.json
{
  "commit_id": "3fc77bdc521f9d67d08a7f4947979b30baf4fd0f",
  "event": "COMMENT",
  "body": "page.tsx guard pattern inline opinion — Critical 1-B downgraded to Important + line-level annotation",
  "comments": [
    {
      "path": "apps/dt/app/site/[siteIndex]/record/pqm/page.tsx",
      "line": 9,
      "side": "RIGHT",
      "body": "⚠️ Potential | 🟡 Important — siteIndex hardcoded guard (Critical → Important downgrade)\n\n`Number(siteIndex) !== 1` is a URL param integer comparison. The sidebar already uses the `siteType === TEST_SITE_TYPE` pattern (master 4982267c, PR #261). Only the page guard departs from this convention.\n\nRecommendation: replace with `useSiteDetail(siteIndex)` + `siteType === 'EQMT-STY01'` check."
    }
  ]
}
```

## Step 7.5: In-Chat Status Statement (MANDATORY — Fact First, Recommendation Second)

After posting the Summary on GitHub, **state the headline status as a single line in chat** before any merge AskUserQuestion or recommendation. The Summary table on GitHub does NOT substitute for plain chat reporting — the user wants the number.

**Format** (one line, no headers):

```text
Status: <addressed>/<total> actionable addressed (<remaining> remaining). CI: <pass|fail|pending>. Test plan: <checked>/<total>. Mergeable: <yes|no|conflict>.
```

**Examples**:

- `Status: 17/17 actionable addressed (0 remaining). CI: pass. Test plan: 6/6. Mergeable: yes.`
- `Status: 4/10 actionable addressed (6 remaining). CI: pass. Test plan: 2/5. Mergeable: yes.`
- `Status: 0/3 actionable addressed (3 remaining). CI: fail. Test plan: 0/4. Mergeable: conflict.`

**Rules**:

- The status line is **required** even when all conditions pass — especially then, because users need to see the explicit "0 remaining" headline.
- The status line precedes any AskUserQuestion. The AskUserQuestion (if any) follows on the next message segment.
- **Never** output "ready to merge" / "merge?" / "squash and merge?" without the preceding status line.
- If conditions are mixed (e.g., 0 actionable but Test plan incomplete), the status line shows the mix; the recommendation respects merge.md's HARD STOP gates.

**Why this exists** (2026-05-04 fix): User feedback "you didn't tell me there are no actionable issues now" — Summary table buried the headline number. Posting Summary is necessary but not sufficient; in-chat status is the user-facing fact.

## Step 7.6: Deferred Actionable immediate registration (MANDATORY — independent of merge option selection)

Right after emitting the status line, **before entering Step 8 next-action ask**, deferred actionable items must be immediately registered to the tracking medium. The "tracking location specification" in Step 8 option descriptions is just a **promise**; in cases where the user does not select a merge option (deferral / carryover to next session), registration does not happen and tracking is missed. **Separate the deferred decision moment from the registration moment** — enforce immediate registration after Summary posting + status line emission.

### Registration target

Among all actionable items from Step 4 classification:
- 🔴 **Critical not addressed** (deferred decision)
- 🟡 **Minor not addressed** (deferred decision — including items withheld as "optional enhancement")
- 🛠️ **Refactor suggestion not addressed** (deferred decision)

⚪ Rejected, 🟢 No issue, and items already addressed immediately are not registration targets.

### Tracking medium (checklist) decision (automatic environment detection)

| Environment detection (based on CWD or workspace) | Medium | Format |
|--------------------------------------|------|------|
| `{workspace}/.ralph/fix_plan.md` exists | `.ralph/fix_plan.md` "On Hold" section (inserted **above** the trailing `## Completed`/`## REPEAT` — never at EOF) | `- [BLOCKED] [REVIEW_FEEDBACK] {reviewer}: {summary} — {action direction, location, PR #N}` |
| `{workspace}/checklist.md` exists (Ralph not used) | `checklist.md` | `- [BLOCKED] [REVIEW_FEEDBACK] {reviewer}: {summary} — {action, PR #N}` |
| Neither exists + GitHub Issue collaboration | New GitHub Issue | `gh issue create` — title `deferred from PR #N: {summary}`, finding details in body |
| Neither exists + no collaboration medium | AskUserQuestion | "Where to register?" options (new `.ralph/fix_plan.md` / new `checklist.md` / Issue / skip registration) |

**Environment detection is workspace (CWD) based** — Do not confuse the project-subdirectory `.ralph/` with the workspace `.ralph/`.

### Registration procedure

1. Read the medium file
2. Locate the "On Hold" / "BLOCKED" section (or an existing active-work section: `TODO`, `Pending`, or the file's priority section)
   - **If absent, insert a new `## On Hold` section ABOVE the trailing `## Completed` / `## REPEAT` sections — never append at end-of-file.** `## REPEAT` is invariantly the last section of `fix_plan.md` (owned by ralph `periodic.md`), so an EOF append silently nests the deferred block under `## REPEAT`, where it is mistaken for a periodic scheduled task
   - Register the deferred items as `-` bullets inside that section. Do **not** create a dangling `###` heading after the last section's list items — a heading placed there becomes a child of whichever `##` section precedes it (i.e. `## REPEAT`)
3. Add N deferred items in batch (Edit)
4. Report the N registered items' medium file path in chat (user-verifiable)
5. **Verify placement**: after the Edit, confirm the nearest preceding `##` heading of the registered items is an active-work section — NOT `## REPEAT` or `## Completed`. If it is one of those, the block landed in the wrong section — move it above the trailing sections

### Don't / Do table

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Assume "register when the user selects a merge option" | Right after emitting the status line, if 1+ deferred items exist, register immediately — independent of user option selection |
| 2 | Substitute Summary notation for registration ("it's tracked since the table marks it as deferred") | Summary is a one-time GitHub comment. Medium (checklist/checklist) registration is separate — preserved on next session reload |
| 3 | Defer registration with "since it's deferred, register next session too" | Defer = tracking medium registration + exposure on next session reload. Without registration, tracking is broken |
| 4 | Autonomously decide "skip registration" in environments with no selected tracking medium | Decide medium via AskUserQuestion. Autonomous skip is forbidden |
| 5 | **Post "Deferred Review Items" as a separate PR comment** | Deferred items go only to the tracking medium (checklist/checklist/Issue). **Posting as a separate PR comment is forbidden** — the Summary table's deferred notation is sufficient |
| 6 | Only output the Step 8 option description promise without any registration action | If the option description promises "checklist.md [BLOCKED] registration", **execute that promise in advance in this step** |
| 7 | Append the deferred block at end-of-file, or as an `###` heading after the last section — it nests under the trailing `## REPEAT` (periodic tasks) or `## Completed` | Insert as `-` bullets under an active-work section (`On Hold`/`BLOCKED`/`TODO`/`Pending`), or a new `## On Hold` section placed **above** `## Completed`/`## REPEAT`. `## REPEAT` holds only `- [REPEAT]` periodic items |

### Self-check (every time before entering Step 8)

1. Are there 1+ deferred actionable items in Step 4 classification? → If yes, this Step 7.6 is required
2. Did the medium decision follow the environment detection table? (Autonomous assumption forbidden)
3. Has registration to the medium file been completed? (verify via Read)
4. Have you reported the number of registered items + medium path in chat?
5. **Placement check**: is the nearest preceding `##` heading of the just-registered items an active-work section (not `## REPEAT` / `## Completed`)? `## REPEAT` is invariantly the last section — an EOF or `###` append nests there. If mis-placed, move above the trailing sections
6. **Promotion PR Body check**: If the PR is a staging promotion PR, did you update the PR body/description with the latest commit list?

## Next

→ `next.md` (Step 8 Post-Summary Next-Action Ask)
