# PR AI Review Consolidation

Review AI bot feedback (CodeRabbit, Copilot, etc.) on a PR and post an AI Review Summary comment.

## When to Use

- After PR creation, when AI reviews are complete
- User says "review check", "CodeRabbit review", "AI review", "review consolidate"
- **Not** for human reviewer feedback — this is AI bot review only
- **Not** for dependabot / bot-authored dependency-bump PRs — consolidate is skipped by principle (Step 2 skip condition 0)

## Role Terminology Definitions (HARD STOP — avoid confusion in conversation/comments)

| Term | Meaning | Example |
|------|---------|---------|
| **author** | The person who created the PR. The party who pushes commits and applies feedback | `<pr-author>` (PR #N) |
| **reviewer** (GitHub) | The person requested to review the PR. Has Formal Review (APPROVE/REQUEST_CHANGES) authority | `<github-reviewer>` |
| **code-reviewer** (subagent) | AI subagent dispatched as Internal Review Fallback | `Agent(subagent_type: "code-reviewer")` |
| **AI reviewer** (bot) | External AI review bots such as CodeRabbit, Copilot | `coderabbitai[bot]` |

| # | Don't | Do (correct alternative) |
|---|-------|--------------------------|
| 1 | Calling the PR author a "reviewer" | "author (`<pr-author>`) applied the commit" — specify role explicitly |
| 2 | "The reviewer pushed a commit" (attributing author's action to reviewer) | "author added a commit applying the review feedback" |
| 3 | Automatically mapping "reviewer" to author when user says it | In consolidate context, "reviewer" defaults to code-reviewer subagent. If ambiguous, AskUserQuestion |

## Workflow Index

| Step | Topic file | Responsibility |
|------|-----------|----------------|
| 1 (Identify PR) + 2 (Skip Conditions) + 2.5 (Copilot sequential) + 2.6 (re-review trigger policy) + 2.7 (worktree checkout) | (inline in this file) | PR identification + skip judgment + Copilot sequential execution + first-vs-re-review classification + check out PR branch into a worktree |
| 3 (Collect AI Reviews) + 3.6 (superpowers:receiving-code-review) | [`collect.md`](./collect.md) | AI review collection + load verify→evaluate→respond framework |
| 3.5 (Internal Review Fallback) + 4.5 (UI capture verification) | [`internal.md`](./internal.md) | Post Internal Code Review comment on walkthrough only/Copilot failure + verify captures on UI-change PRs |
| 4 (Analyze and Classify) | [`classify.md`](./classify.md) | dual-label (Type \| Severity) classification + PR diff scope cross-check + option grouping |
| 5 (Formal Review Decision — Axis B only) + 6 (Fix or Reject — only on explicit instruction) | [`decide.md`](./decide.md) | Axis B (Formal Review) ask when requested reviewer. **Axis A (Findings handling) ask is forbidden (HARD STOP)** — posting the Summary is procedure |
| 7 (Auto-Post AI Review Summary + Formal Review) + 7.5 (Status line) + 7.6 (Auto-register Deferred Findings) | [`post.md`](./post.md) | Auto-post the Summary (no user decision) + auto-register Findings to fix_plan `[REVIEW_FEEDBACK]` (defer by default) |
| 8 (Post-Summary Next-Action Ask) | [`next.md`](./next.md) | Merge/fix-deferred/hold option ask (fix only on explicit user instruction at this step) |

Entry order: Step 1 → 2 → **2.3** (duplicate-review check, three axes — submitted human reviews + pending requests + foreign AI Summary; ask before proceeding on any hit) → **2.4** (Copilot availability pre-check, always) → (2.5 multi-PR only, skipped if 2.4 = not available) → 2.6 (re-review trigger classification, always) → 2.7 (worktree checkout) → [collect](./collect.md) → [internal](./internal.md) (conditional fallback, auto-routed when 2.4 = not available) → [classify](./classify.md) → [decide](./decide.md) → [post](./post.md) → [next](./next.md).

## Step 1: Identify PR

If no PR number given, detect from current branch:

```bash
gh pr list --head "$(git branch --show-current)" --json number,title --jq '.[0]'
```

**Confirm owner/repo first (HARD STOP)**: before identifying the PR, run `git remote get-url origin` to pin the exact `<owner>/<repo>`, and pass `-R <owner>/<repo>` on every downstream `gh` call. When multiple worktrees/workspaces share the same basename (e.g. two `web` checkouts under different orgs), relying on cwd alone can target another repo's PR of the same number.

## Step 2: Check Skip Conditions

Skip entirely if any of these are true:

0. **Bot-authored dependency-bump PR (HARD STOP — skip by principle)**: `gh pr view <NUMBER> --json author --jq '.author.login'` matches a dependency bot (`dependabot`, `renovate`, etc.) → the entire consolidate flow is skipped. CI green + the bot's own compatibility data + the lockfile-consistency gate ARE the verification — no worktree checkout, no CLI/agent review, no Internal Review, no Summary, no Formal Review. The merge decision goes directly to the user with CI/lockfile attestation instead of an AI Review Summary. **Override**: run consolidate on such a PR only when the user explicitly requests a review of it (e.g., a major-version bump they want inspected).
1. **CI failing**: `gh pr checks <NUMBER> --json state --jq '[.[] | select(.state != "SUCCESS")] | length'` > 0
2. **Reviews not complete**: CodeRabbit summary comment not yet posted (check for "<!-- walkthrough_start -->")
3. **Already summarized**: `gh pr view <NUMBER> --comments` contains "AI Review Summary"
4. **Draft PR (HARD STOP — no exception for "no findings" framing)**: `gh pr view <NUMBER> --json isDraft --jq '.isDraft'` returns `true` → skip the entire flow, including Step 7. A draft PR has not opted into review (CodeRabbit/Copilot commonly skip drafts by their own config, matching Step 2 condition 2's "reviews not complete"). **Do not post a Summary that documents the absence of review** ("no findings", "eligible for no-review merge", etc.) — an absent review is not a reviewed-and-clean verdict, and posting one anyway defeats condition 2's intent through a side door. Re-run consolidate after the PR transitions to ready (`gh pr ready <NUMBER>`).
5. **Non-default base branch used for staged/pre-merge batching** (project-specific — check the project's own branch-promotion convention, e.g. a staging branch that later opens its own promotion PR into the default branch): skip Summary/Formal Review for the same reason as condition 4 — the review gate for that PR's actual content sits on the later promotion PR, not this one. If the project has no such convention, this condition does not apply.

> **Bash exit code caveat**: `grep -c` returns exit code 1 when there are zero matches. When chaining multiple commands with `grep` last, add a `|| true` guard to prevent false-positive errors.

If skipped, report the reason and stop.

## Step 2.3: Duplicate-review check (HARD STOP — three axes, ask before proceeding on any hit)

**Before collecting reviews / dispatching the Internal Review, check whether someone outside your own gh-authenticated account set is already involved as a reviewer on the PR — on any of three axes.** A hit on any axis signals the author wants (or already has) that person's review — running an autonomous AI consolidate would be redundant or step on their role.

"Me / us" = every account listed by `gh auth status` (acting account + review proxies). Bots (CodeRabbit / Copilot / actions / dependabot) are excluded — they belong to the Step 2.4 bot matrix, not this gate.

```bash
# my authenticated accounts (portable — no hardcoded names)
MY=$(gh auth status 2>&1 | grep -oiE 'account [A-Za-z0-9_-]+' | awk '{print tolower($2)}' | sort -u | tr '\n' '|' | sed 's/|$//')
BOTS='coderabbit|copilot|github-actions|dependabot|\[bot\]|-bot$'

# axis 1 — submitted reviews by someone else (submission EMPTIES reviewRequests — check reviews[] first)
gh pr view <N> -R <owner>/<repo> --json reviews \
  --jq ".reviews[].author.login" | grep -viE "^(${MY})$|${BOTS}" | sort -u

# axis 2 — pending requested reviewers (assigned but not yet submitted)
gh pr view <N> -R <owner>/<repo> --json reviewRequests \
  --jq ".reviewRequests[].login" | grep -viE "^(${MY})$|${BOTS}" | sort -u

# axis 3 — AI Review Summary / Internal Code Review comment authored by someone else
gh pr view <N> -R <owner>/<repo> --json comments \
  --jq '.comments[] | select(.body | test("AI Review Summary|Internal Code Review|Internal Review";"i")) | .author.login' \
  | grep -viE "^(${MY})$|${BOTS}" | sort -u
```

If **any** axis is non-empty, **AskUserQuestion before proceeding**, with options:
- **Proceed with AI consolidate anyway** — the AI review supplements the existing/expected review
- **Defer to the existing reviewer** — skip AI consolidate; their review stands
- **Hold** — decide later

Do not silently run the Internal Review + Summary on any axis hit. The bot reviewer matrix (CodeRabbit/Copilot, Step 2.4) is a **separate** check — this gate is specifically about **humans and foreign accounts**.

**Autonomous / dispatched context**: a dispatched autonomous session has no ask medium, so this gate must run **pre-dispatch in the host session** (the dispatching orchestrator may wrap the three axes in a script that exits CLEAR/BLOCK). A "Step 2.3 cleared" pre-baked waiver in the dispatch instruction is valid only when it quotes that pre-dispatch gate's CLEAR verdict for the same PR; otherwise the session must run the queries above itself and treat any hit as a terminal blocker (report and stop — no Summary post).

| # | Don't | Do |
|---|-------|-----|
| 1 | See `reviewRequests: []` and conclude "no reviewer involved" | Submission removes the reviewer from `reviewRequests` — axis 1 (`reviews[]`) catches already-submitted reviews. Run all three axes |
| 2 | Hardcode account names ("not daegunjhy") in the filter | Derive "me" from `gh auth status` — portable across machines and account changes |
| 3 | Treat `reviewRequests` as relevant only to the bot reviewer matrix | Bot reviewers (Step 2.4) and human/foreign reviewers (this step) are separate. Any axis hit gates the whole consolidate |
| 4 | "I am the author, so I run consolidate regardless of who else reviews" | Author running AI consolidate while another reviewer is involved = potential redundancy/overstep → ask |
| 5 | Skip axis 3 because "comments are not reviews" | A foreign AI Review Summary means another operator's consolidate already ran — a second Summary duplicates and may contradict it |

### Self-check (before Step 2.4 / Step 3 collect)

1. Did you run all **three** axis queries with the `gh auth status`-derived account filter (acting account + proxies + bots excluded)?
2. Is any axis non-empty? → If yes, did you AskUserQuestion (proceed/defer/hold) **before** any Internal Review dispatch or Summary post? (Autonomous session: any hit = terminal blocker — report and stop)
3. If all three axes are empty (only bots or just you) → proceed normally.

## Step 2.4: Copilot availability pre-check (HARD STOP — auto-fallback, no ask)

**GitHub Copilot Code Review is a paid subscription as of 2025.** Without an active subscription on the acting account or the repo's organization, adding `copilot-pull-request-reviewer` as a reviewer fails silently or returns 422. **Run Step 2.4.0 (existing-review check) FIRST; only when no Copilot review already exists do you check availability BEFORE Step 2.5 sequential trigger or Step 2.6 re-review trigger. On unavailable (and no existing review) → automatically route to Internal Review Fallback (Step 3.5) WITHOUT AskUserQuestion.**

### Step 2.4.0: Existing Copilot review check FIRST (HARD STOP — precedes availability detection)

**Before running any billing/availability signal, check whether a completed Copilot review ALREADY EXISTS on this PR.** The availability pre-check answers "can I *request* a new Copilot review?" (billing/subscription) — it does NOT answer "is there a Copilot review to *collect*?" (existence on the PR). A review may already be present (triggered by the author's account, a repo-level Copilot setting, or a prior session) even when the acting account's billing endpoints return 404 / seat 0. Treating billing-unavailable as "no Copilot review to collect" silently skips an existing review.

```bash
# Both API surfaces — GraphQL drops the [bot] suffix, REST keeps it (see collect.md surface caveat)
gh pr view <N> -R <owner>/<repo> --json reviews \
  --jq '[.reviews[] | select(.author.login | test("copilot"; "i"))] | length'
gh api repos/<owner>/<repo>/pulls/<N>/reviews \
  --jq '[.[] | select(.user.login | test("copilot"; "i"))] | length'
```

- Result `≥1` → **a Copilot review exists. It is a Step 3 collect target regardless of billing.** Skip the billing-based availability detection + auto-fallback below; record Copilot as a present reviewer in the Summary matrix and collect its findings (review body + inline comments via `.../pulls/<N>/comments`) in Step 3. Internal Review (Step 3.5) may still run as an independent second perspective, but Copilot is NOT "unavailable".
- Result `0` → no existing Copilot review → proceed to the availability detection below (which decides whether to *request* one).

| # | Don't | Do |
|---|-------|-----|
| 1 | Run billing signals first → 404 / seat 0 → declare "Copilot unavailable" → auto-fallback, skipping the existing Copilot review already on the PR | Check for an existing Copilot review FIRST. Present → collect it (billing is moot). Absent → then run billing to decide whether to request one |
| 2 | Equate "acting account's billing = unavailable" with "no Copilot review to collect" | Billing = can-I-request. Existence-on-PR = is-there-one-to-collect. A review triggered under the author's account / repo setting exists independent of the acting account's seat |
| 3 | Query only `gh pr view --json reviews` (GraphQL, no suffix) and miss the REST-surface login | Copilot login differs by API surface (`copilot-pull-request-reviewer` vs `...[bot]`). Use a `test("copilot"; "i")` substring match on both surfaces |

### Availability detection (primary-source signals — confirm via at least one)

| # | Signal | Command | Interpretation |
|---|--------|---------|----------------|
| 1 | User-level subscription | `GH_TOKEN="$(gh auth token --user <account>)" gh api /user/copilot_billing 2>&1` | 200 with `seat_breakdown` → available. 404 / "Not Found" → **not available** |
| 2 | Org-level subscription (org repos only) | `GH_TOKEN="$(gh auth token --user <account>)" gh api /orgs/<org>/copilot/billing 2>&1` | 200 with `seat_breakdown.total` > 0 → available for org members. 404 / 403 → **not available** |
| 3 | Past behavior on this repo | `gh pr list -R <owner>/<repo> --state all --limit 20 --json reviews --jq '[.[].reviews[]? | select(.author.login == "copilot-pull-request-reviewer")] | length'` | `>0` → repo has historically used Copilot review (likely available). `0` → no historical evidence (unknown) |

**Decision tree** (evaluate in order — each step's exit condition is exclusive):

1. **Fork / cross-org guard (runs BEFORE signal 1's short-circuit)**: if the PR's repo is `isCrossRepository: true` OR `headRepositoryOwner != baseRepositoryOwner`, run signal 3. `0` historical Copilot reviews on this repo → **not available** → auto-fallback to Internal Review (Step 3.5), skip Step 2.5/2.6. `>0` → continue to step 2 (user's subscription may apply on this repo because the bot has reviewed here before).
2. Run signal 1 (user-level). If 200 with active seat → **available** (skip to Step 2.5/2.6).
3. If signal 1 = 404:
   - **Org-owned repo** → run signal 3.0: signal 2 (org-level). If 200 with `seat_breakdown.total > 0` → **available**. If 404 / 403 → **not available** → auto-fallback to Internal Review (Step 3.5).
   - **User-owned (non-org) repo** → run signal 3 (historical evidence). `>0` → assume **available** (the user previously had a Copilot subscription that worked on this repo). `0` → **not available** → auto-fallback.
4. Network/auth errors during the check → assume not available (fail safe to Internal Review).

### Auto-fallback (no AskUserQuestion)

When Step 2.4 concludes "not available", **route DIRECTLY into Step 3.5 Internal Review Fallback**. Do NOT:

- Call `AskUserQuestion` asking "Copilot or Internal Review?" — the user already pays the cost of the question by losing time to a forced decision they cannot change (subscription is out-of-band)
- Wait for the user to explicitly say "use internal review" — that was the prior policy and it is now deprecated
- Attempt Copilot reviewer add anyway "to see what happens" — it consumes API quota and emits user-visible noise on the PR if it partially succeeds

| # | Don't | Do |
|---|-------|-----|
| 1 | Skip Step 2.4 → directly call Step 2.5 sequential → silent Copilot reviewer add fails → wait indefinitely | Run Step 2.4 first. On unavailable → Step 3.5 Internal Review automatic |
| 2 | On Step 2.4 unavailable result → AskUserQuestion "Copilot or Internal Review?" | Unavailable is a primary-source fact (subscription state). No ask — auto-route to Internal Review |
| 3 | Report "Copilot unavailable, proceeding with Internal Review" and stop, waiting for user OK | Report the same line **and continue executing Step 3.5** in the same turn. The report is a transparency note, not a gate |
| 4 | Interpret 404 from `/user/copilot_billing` as "auth issue, retry with elevated scope" | 404 on this endpoint = no Copilot subscription (the endpoint exists and returns 404 only when the resource is absent). Treat as authoritative |
| 5 | Cache availability across sessions ("user had no Copilot 2 weeks ago, still no") | Subscription can change. Run signal 1 every consolidate invocation. The check is one `gh api` call — cost is negligible |
| 6 | When historical evidence (signal 3) shows past Copilot reviews on this repo but signal 1/2 returns 404 → assume "the bot was kicked off, manually add it back" | Past behavior is informational. Authoritative state is signal 1/2. If they return 404 → not available now → fallback |

### Self-check (every time before Step 2.5/2.6 entry)

0. **Did you run Step 2.4.0 (existing-Copilot-review check) FIRST, before any billing signal?** A review already present on the PR = collect target regardless of billing → skip availability detection + auto-fallback for that reviewer. Billing decides only whether to *request* a NEW review when none exists.
1. Did you run signal 1 (`/user/copilot_billing`) in this consolidate session?
2. If signal 1 returned 404/error → did you check signal 2 (org billing) when the repo is under an org?
3. If signal 1+2 both indicate unavailable → did you skip Step 2.5/2.6 and route DIRECTLY into Step 3.5?
4. Did you avoid calling AskUserQuestion for "Copilot vs Internal Review" branching? (Auto-fallback policy — ask forbidden)
5. Did you record the unavailable-status note in the eventual AI Review Summary's reviewer matrix (so the reader knows why Copilot is absent)?

### Reporting note (include in Summary reviewer matrix)

When availability check returns "not available", the AI Review Summary's reviewer matrix should include a row noting the substitution. Example:

```markdown
> Reviewer matrix: **CodeRabbit** (walkthrough + actionable) + **Internal Code Review** (Copilot unavailable on the acting account/org — auto-fallback per Step 2.4).
```

This preserves transparency: the reader sees Copilot absence as a deterministic policy result, not as a missed review.

## Step 2.5: Sequential Copilot Review Execution (when consolidating multiple PRs)

When consolidating multiple PRs and Copilot review requests are needed:

1. **Search the checklist for `[COPILOT_PENDING]`** — verify whether a previously requested review is still in progress
2. **If PENDING exists, check that PR**: use `gh pr view <N> --comments` to confirm whether the Copilot review is complete
   - Complete → update checklist `[COPILOT_PENDING]` → `[COPILOT_DONE]`
   - Incomplete → wait (do not submit new requests on other PRs)
3. **When no PENDING exists or after confirming completion**: also check the Copilot review status of the remaining open PRs (`gh pr list --state open`) and batch-update the checklist
4. **Request a Copilot review on only one next PR** → record `[COPILOT_PENDING] PR #N` in the checklist

> **History of repeated failures**: 2026-04-27 batch invocation of 7 reviews all failed; 2026-04-28 parallel review depleted quota

## Step 2.6: Re-review trigger policy (HARD STOP — first review vs re-review)

**Applies to every PR consolidate flow, single-PR or multi-PR.** Distinguishes first AI bot review (triggered by PR creation) from re-review (triggered by a fix commit on an already-reviewed PR).

| Scenario | Bot trigger autonomy |
|----------|---------------------|
| First review (no prior review from this bot exists on the PR) | Autonomous — PR creation itself is the user trigger |
| **Re-review** (≥1 prior review from this bot exists; new commit pushed) | **AskUserQuestion required** before any bot trigger |
| **Re-review with NO new commits since the bot's last review evidence** | **Forbidden — no-op + noise.** CodeRabbit is an incremental reviewer and "does not re-review already reviewed commits". Nothing to trigger |

### Review-completion state matrix (classify BEFORE any trigger decision)

A bot review is judged complete/incomplete by these signals — misreading a completed state as "absent" is what causes redundant re-triggers:

| State | Signal | Action |
|-------|--------|--------|
| **Completed — findings** | Walkthrough/summary comment + actionable inline comments, or formal review with findings | Proceed to collect |
| **Completed — zero findings (terminal)** | CodeRabbit summary comment "**No actionable comments were generated in the recent review**" (walkthrough may be collapsed inside the same comment); Copilot COMMENTED review with no blocking items | **Review IS complete, verdict = 0 findings. Never re-trigger.** Proceed to collect/classify with a clean verdict |
| **In progress** | Status check "Review in progress" / bot activity within ~10 min | Wait — poll, do not trigger |
| **Absent** | No comment/review/status from the bot after PR ready + reasonable wait | Re-review policy above applies (first review = autonomous; otherwise ask) |

"Bot trigger" includes:

- `gh api repos/<o>/<r>/pulls/<N>/requested_reviewers -X POST -f reviewers[]=<bot>`
- `gh pr edit <N> --add-reviewer <bot>`
- `gh pr comment <N> --body "/review"` or `@coderabbitai review` (slash command)

### Pre-trigger self-check (every time before issuing a re-review trigger)

> **Placeholder note**: throughout this section, `<bot>` is a substitution token — replace it with the bot login substring (e.g., `coderabbit` for CodeRabbit, `copilot` for Copilot). Without substitution the `test("<bot>"; "i")` filter matches nothing.

1. **First-vs-re-review classification** — count prior review **evidence** (formal reviews AND comments) from the target bot:
   ```bash
   gh pr view <N> -R <owner>/<repo> --json reviews,comments \
     --jq '([.reviews[] | select(.author.login | test("<bot>"; "i"))] | length)
         + ([.comments[] | select(.author.login | test("<bot>"; "i"))
             | select(.body | test("walkthrough_start|summarize by coderabbit|No actionable comments"))] | length)'
   ```
   `0` = first review case (autonomy OK). `>0` = re-review case (ask required).

   > **Why comments too**: CodeRabbit posts its review output as **issue comments** (walkthrough / summarize / zero-findings verdict), not formal reviews. A reviews-only count returns `0` on a fully completed CodeRabbit review → misclassifies a re-review as a first review → bypasses the ask gate.

1.5. **New-commit check (re-review case)** — a re-review trigger is meaningful only if commits exist AFTER the bot's last review evidence:
   ```bash
   gh pr view <N> -R <owner>/<repo> --json commits,comments \
     --jq '{lastCommit: ([.commits[].committedDate] | max), lastBotEvidence: ([.comments[] | select(.author.login | test("<bot>"; "i")) | .createdAt] | max)}'
   ```
   `lastCommit < lastBotEvidence` → **no new commits since the review — do NOT trigger** (incremental reviewers skip already-reviewed commits; the trigger is pure noise).

2. **In-progress review check (mandatory in re-review case)** — confirm the bot is not already working:
   ```bash
   # CodeRabbit: status check entry signals in-progress
   gh pr checks <N> -R <owner>/<repo> | grep -E "CodeRabbit|copilot" || true
   # Bot status comments / draft reviews
   gh pr view <N> -R <owner>/<repo> --json comments \
     --jq '[.comments[] | select(.author.login | test("<bot>"; "i")) | select(.createdAt >= (now - 600 | strftime("%Y-%m-%dT%H:%M:%SZ"))) | .body[:120]]'
   ```
   In-progress signal present (status text such as "Review in progress", or recent activity within ~10 min) → **do not trigger**. Wait — autonomous poll is allowed, autonomous trigger is not.

3. **AskUserQuestion before trigger** — options must include:
   - Re-request bot review (only if no in-progress signal)
   - Skip bot — proceed with prior review + apply-evidence
   - Hold

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat a user instruction to "wait for re-review" as license to trigger the bot autonomously so the review arrives | "Wait" means poll, not trigger. Bot trigger requires AskUserQuestion regardless of the user's polling intent |
| 2 | One missed poll → re-request → another /review comment → another POST (cascading triggers) | Single AskUserQuestion at the first missing-arrival decision point. No cascade |
| 3 | Skip the in-progress check before re-requesting | In-progress check is mandatory. Active reviewer must not be re-triggered |
| 4 | Re-trigger because the first review found N findings and all were fixed — re-review will be quick | Volume/quality of fix is irrelevant. Re-trigger autonomy is determined by user ask, not by perceived cost |
| 5 | Treat slash commands (`/review`, `@coderabbitai review`) as not-a-trigger because they look conversational | Slash commands trigger the bot identically. Same ask rule applies |
| 6 | Read "No actionable comments were generated in the recent review" as "review missing / walkthrough absent" → trigger a review | That message IS the completed review (terminal state, verdict 0 findings — see the state matrix above). Proceed to collect with a clean verdict |
| 7 | Bot replies "does not re-review already reviewed commits" after a trigger → fire another trigger variant (`full review`, second comment, reviewer re-add) | That reply is a **terminal stop signal**. Zero further triggers — proceed with the existing review output |
| 8 | Trigger a re-review when no commits exist after the bot's last review evidence | Run the new-commit check (self-check 1.5) first. No new commits = nothing for an incremental reviewer to review |

**Enforcement hook**: `~/.agents/skills/hook-kit/resources/block-bot-re-trigger.sh` (PreToolUse:Bash) denies bot re-trigger commands when prior review evidence exists on the PR. After an explicit user approval via AskUserQuestion, prefix the command with `BOT_RETRIGGER_APPROVED=1` to pass the gate.

### Rate-limit retrigger discipline (any bot rate-limit rejection)

When a bot responds with a rate-limit rejection instead of a review (e.g., CodeRabbit "Review limit reached — **Next review available in:** N minutes"), triggering again is allowed only under this discipline:

1. **Parse the deadline**: rejection comment `created_at` + N minutes → deadline. Do NOT treat N as approximate — windows are enforced to the second.
2. **Retrigger no earlier than deadline + 60s margin.** A single computed retrigger per window.
3. **On re-rejection, re-parse the REFRESHED comment**: the bot updates the same rejection comment with a new remaining time — the clock restarts from its `updated_at`. Never reuse the first estimate.
4. **Poll with positive markers**: the refreshed comment no longer contains "Review limit reached", the walkthrough marker appears, or the review artifact count > 0. Negative predicates over multiline bodies (`grep -qv`) match almost anything and are always-true traps.

| # | Don't | Do |
|---|-------|-----|
| 1 | Trigger "roughly when the window should be open" without computing `created_at` + N | Compute the deadline from the rejection comment timestamp, add a 60s margin, then trigger once |
| 2 | On re-rejection, keep waiting against the original estimate | Re-parse the refreshed rejection comment's "available in N minutes" from its `updated_at` |
| 3 | Poll completion with a negative multiline grep (`grep -qv 'rate limited'`) | Poll for positive markers (limit text absent from the refreshed body / walkthrough present / reviews count > 0) |
| 4 | Fire retriggers repeatedly until one sticks (burns external quota + PR timeline noise) | One computed retrigger per window; if state is uncertain, wait for the next poll cycle instead of triggering |

## Step 2.7: Checkout PR branch into a worktree (MANDATORY — all reviews)

After skip conditions pass, check out the PR's head branch into a local worktree **before** collecting reviews. Every review runs against real local files, not just `gh pr diff`. Benefits: the code-reviewer (Step 3.5) reads actual files + can run tests/build, `mergeable: CONFLICTING` is confirmed locally, and inline review line numbers (Step 7) match HEAD exactly.

### Procedure

1. **Resolve PR head branch + base + cross-repo flag**:
   ```bash
   gh pr view <N> -R <owner>/<repo> \
     --json headRefName,headRefOid,baseRefName,mergeable,isCrossRepository,headRepositoryOwner \
     --jq '{branch: .headRefName, head: .headRefOid, base: .baseRefName, mergeable, fork: .isCrossRepository, headOwner: .headRepositoryOwner.login}'
   ```
   - `base` (`baseRefName`) is the merge target — needed for the CONFLICTING detection step below.
   - `fork` (`isCrossRepository`) flips the fetch strategy in step 3.
2. **Acquire a worktree via the `git-repo` `worktree` topic** — do NOT `git worktree add` blindly. Follow git-repo's decision tree: reuse an inactive / merged-PR worktree first (rename to this PR's branch), else create at `.claude/worktrees/<branch>`. (`git-repo` is a `depends-on` of this skill.) Record the worktree path; all subsequent steps operate there.
3. **Fetch head + base** (inside the worktree from step 2):
   - **Same-repo PR** (`fork == false`): `git -C <worktree> fetch origin <headRefName> <baseRefName>` — both refs live on `origin`.
   - **Fork PR** (`fork == true`): `origin` does not carry the fork's head. From inside the worktree, `gh pr checkout <N> -R <owner>/<repo> --force` creates a local tracking branch from the fork via the API. Then `git -C <worktree> fetch origin <baseRefName>` for the base. (`gh pr checkout` does not recurse submodules by default — no extra flag needed.)
4. **The worktree path is now the operating directory for the rest of the workflow**: the code-reviewer dispatch (Step 3.5) gets this path, local verification runs in it, and Step 7 inline line lookups read files from it.

### CONFLICTING detection (report, do not resolve)

If `mergeable` is `CONFLICTING`, the worktree lets you confirm the conflicting files locally (uses `baseRefName` resolved in step 1):

```bash
git -C <worktree> merge --no-commit --no-ff origin/<baseRefName> 2>&1 | grep -i conflict
git -C <worktree> merge --abort   # always abort — do not commit a merge into the PR branch
```

Report the conflicting files in the Summary so the author can rebase. **Do not resolve another author's conflict** (branch ownership: only the PR author resolves — see `~/.agents/rules/git.md` "Branch ownership" rule).
**Exception for Staging Promotion PRs (e.g. next-fix / next-feat)**: If all blocking/ready PRs are already merged, and the promotion PR is conflicting with `main`, the operator should resolve the conflict by merging `origin/main` (or the base branch) into the promotion branch, resolving the conflicts, and pushing the update to origin.

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Review only from `gh pr diff` with no local checkout | Check out the PR branch into a worktree first; the code-reviewer reads real files + runs tests |
| 2 | `git worktree add` a fresh worktree every review | Use the git-repo `worktree` topic — reuse inactive / merged-PR worktrees first (decision tree) |
| 3 | Resolve a CONFLICTING PR's conflict in the worktree (except for staging promotion PRs) | Detect + report conflicting files. Branch ownership: only the author resolves (unless it is a staging promotion PR with all blockers merged) |
| 4 | `git worktree remove` after every review | Leave it for git-repo to reuse next review. Do not delete blindly |
| 5 | Skip the worktree when external AI review is already sufficient | Worktree is mandatory for **all** reviews — it enables CONFLICTING detection + local verification regardless of external AI completeness |

### Self-check (before Step 3 collect)

1. Did you resolve `headRefName` and fetch it?
2. Did you acquire the worktree via git-repo's worktree topic (reuse-first), not a blind `git worktree add`?
3. Is the worktree path recorded for the code-reviewer dispatch + inline lookups?
4. If CONFLICTING, did you confirm the conflicting files locally and abort the test-merge?

## Rules

- **PATCH the same comment when updating; never add a parallel comment + overwrite the old one (HARD STOP)**: If a previous session's Internal Review/AI Review Summary comment already exists on the same PR, update **that same comment** in place via `gh api PATCH` with the new same-kind content (Internal Review → Internal Review update; Summary → Summary update). PATCHing the same comment with same-kind content is the intended use — the prior content is replaced, but no other comment is touched. **What is forbidden**: adding a new comment AND then PATCHing the previous comment's body with placeholder/minimize text (e.g., `_(minimized)_`) to "hide" the old one — that permanently destroys the original content of the previous comment.

  | # | Don't | Do (correct alternative) |
  |---|-------|--------------------------|
  | 1 | Adding a new `gh pr comment` when a same-kind comment already exists | Update the existing comment with `gh api repos/{owner}/{repo}/issues/comments/{id} -X PATCH -f body=...` (same-kind content) |
  | 2 | Adding a new comment then PATCHing the previous comment body with placeholder/minimize text | Do not touch the previous comment. If a new comment is needed, keep the previous one intact |
  | 3 | Overwriting the previous comment body with `_(minimized)_` to "hide" it | Preserve the original previous comment. If folding is needed, use GraphQL `minimizeComment(classifier: OUTDATED)` (which does not modify the body) |

- **Never auto-fix without explicit user instruction** — fix (code changes) must not run automatically in Step 5/6. Proceed only when the user explicitly chooses "fix" in the Step 8 next-action ask. Posting the Summary (Step 7) is procedure, so it proceeds automatically without a user decision
- **Never auto-commit/push without user approval** — even after a fix is decided, commit/push needs separate explicit consent
- **Always post summary comment automatically** — regardless of whether actionable items exist, **once Step 2 is passed** (draft / non-default-base-staging PRs are skipped at Step 2 condition 4/5, never reach this rule). Findings are auto-registered to fix_plan in Step 7.6. Asking whether to post the Summary is forbidden (HARD STOP). For the medium, see the "Medium selection" table in [`post.md`](./post.md)
- **Check branch ownership** — only modify code on self-created branches
- **Formal Review is mandatory when you are a requested reviewer** — issue comment Summary alone does not satisfy the review request
- **One summary per PR** — skip if "AI Review Summary" already exists. On re-run, update via PATCH on the existing comment
- **Verify before accepting** (`superpowers:receiving-code-review`) — grep actual usage, check callers, confirm the suggestion doesn't break existing behavior
- **No blind acceptance** — each Actionable item needs a verification note explaining why it's valid
- **Push back when wrong** — technically incorrect or YAGNI suggestions get Rejected with reasoning, not silently accepted
- **Copilot review requests must be one PR at a time** — parallel requests only deplete quota and may all fail
  - **Status tracking**: when requesting a Copilot review, record `[COPILOT_PENDING] PR #N` in the checklist
  - **Pre-request check**: if the checklist contains `[COPILOT_PENDING]`, first verify whether that PR's review is complete
  - **After confirming completion**: update `[COPILOT_PENDING]` → `[COPILOT_DONE]`, audit all remaining open PRs and batch-update Copilot status in the checklist, then request a review on the next PR
