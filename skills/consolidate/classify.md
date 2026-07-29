# Analyze and Classify

Classify each finding using the verify→evaluate→respond pattern. Apply PR diff scope cross-check + option grouping + dual-label (Type | Severity).

Entry: `Skill("consolidate", "classify ...")` or `pr.md` Workflow Step 4.

## Step 4: Analyze and Classify (verify before accepting)

For each feedback item, apply the **verify→evaluate→respond** pattern loaded from `superpowers:receiving-code-review`:

1. **READ**: Complete feedback without reacting
2. **VERIFY**: Check against codebase reality — `grep` for actual usage, read the implementation being criticized
3. **EVALUATE**: Is this technically sound for THIS codebase? YAGNI check — if the suggestion adds unused functionality, classify as Rejected

> **The `receiving-code-review` load is justified ONLY by producing explicit validity verdicts (Step 4-0) — including ⚪ Rejected where warranted.** If a consolidate run defaults every finding to Deferred and produces zero Reject consideration, the skill load was decorative: the framework's core verb is "push back when wrong", not "defer everything". A Summary with no Reject path exercised does not need `receiving-code-review` at all.

### Step 4-0: Validity verdict (MANDATORY — operationalize receiving-code-review, runs BEFORE 4-A/Severity)

**Validity (valid vs reject) and timing (now vs defer) are SEPARATE axes. Every finding must get an explicit validity verdict FIRST.** Timing (immediate fix / Deferred) applies **only to findings already judged VALID**. A wrong / inapplicable finding is ⚪ **Rejected** — it must NOT be silently carried as "Deferred" (Defer is a timing decision for valid findings, never a substitute for the Reject validity verdict).

Per finding, record one verdict:

| Verdict | When | Next |
|---------|------|------|
| ✅ **VALID** | Verified correct for THIS codebase | → Step 4-A scope + Severity + timing (now/defer) |
| ⚪ **REJECTED** | One of the Reject reasons below holds | → pushback track (reason mandatory; NOT carried into apply/defer groups) |

**Reject reasons (any one ⇒ ⚪ Rejected — not Deferred):**

1. **YAGNI** — adds unused functionality (grep confirms no caller / no need)
2. **Technically inappropriate** — wrong for this stack/platform/version
3. **Contradicts the author's deliberate or documented intent** — the PR/commit/issue shows the author intentionally chose the criticized structure (e.g., a deliberately-built merge/TDD structure, an explicit architectural decision). A reviewer preference against a deliberate author choice is Rejected, not Deferred
4. **False premise** — VERIFY failed: the finding's factual claim is wrong (e.g., "PR introduced regression in X" but `git log <base>..HEAD -- X` is empty — see Step 4-A #7)
5. **Already handled elsewhere** — the concern is covered by existing code/middleware/tests the reviewer missed

| # | Don't | Do |
|---|-------|-----|
| 1 | Default a finding to `🟡 Deferred` without a validity verdict | Assign VALID or ⚪ REJECTED first. Defer only a VALID finding |
| 2 | Carry a wrong / author-contradicting finding as "Deferred (author follow-up)" | A wrong finding is ⚪ Rejected with reason. Deferring it dumps invalid work on the author |
| 3 | Produce a Summary where every finding is Deferred and none was Reject-considered | That means `receiving-code-review` was loaded but unused (decorative). Each finding's verdict must show the validity judgment was actually made |
| 4 | Treat "Reject" as confrontational and soften to Defer | Reject with a one-line technical reason is the honest verdict the framework requires ("push back when wrong") |

**Self-check (before Step 4-A / Severity / option construction):**

1. Does **every** finding have an explicit VALID or ⚪ REJECTED verdict? (no finding reaches Severity/timing without it)
2. For each ⚪ REJECTED, is exactly one Reject reason (1–5 above) cited in one line?
3. Did you actively consider the Reject path for each finding — not just default to VALID→Defer? (If zero findings were even Reject-evaluated, re-run this step — the `receiving-code-review` load is otherwise decorative)
4. Are any "Deferred" findings actually Reject candidates (wrong / contradicts author intent / false premise)? → reclassify to ⚪ Rejected

### Step 4-A: PR diff scope cross-check (MANDATORY before classifying deferred)

**Before classifying any finding, cross-check the finding's file path against the result of `gh pr view <N> --json files` (the list of files this PR actually modified).** If the file referenced by the finding is **included in the PR diff, the "outside PR scope" label is forbidden** — classify it as an immediate fix candidate within the same PR.

```bash
# Collect PR diff file list (run once before classification)
GH_TOKEN="$(gh auth token --user <account>)" gh pr view <N> -R <owner>/<repo> --json files --jq '.files[].path' | sort > /tmp/pr-${N}-files.txt
```

After cross-checking, explicitly mark the **scope label** in the finding classification report:
- ✅ **In diff** — finding file is inside the PR diff. Immediate fix candidate (deferred default is forbidden regardless of Severity)
- ❌ **Outside diff** — finding file is outside the PR diff. May be classified as deferred

#### Don't / Do table (HARD STOP — PR scope inference forbidden)

| # | Don't | Do |
|---|-------|-----|
| 1 | Inferring "this is only scope X" from PR title/branch name (`spike/`, `feat:`, etc.) → classifying findings on other files as deferred | Measure with `gh pr view --json files` → if finding file is in diff, "outside PR scope" label is forbidden |
| 2 | Asserting "this is a spike PR, so packages/web changes are external work" | Even in a spike PR, if packages/web files are in the diff, that part is within the same PR scope |
| 3 | Autonomously judging "this finding naturally belongs in a separate PR" | Scope is a user decision. For findings inside the diff, include "immediate fix" as the default option candidate |
| 4 | Automatically deferring when Severity is Minor | Severity and scope are separate dimensions. Minor + In diff = immediate fix possible. Only Minor + Outside diff defaults to deferred |
| 5 | Deferring because "this file seems unrelated to the PR" | "Seems" is not a judgment. Measure with `gh pr view --json files` |
| 6 | Using `git diff <base>..HEAD --name-only` (two-dot, bidirectional) as the PR scope source | Two-dot includes files that `<base>` has but `HEAD` does not (i.e., main's later changes that PR did not absorb). Use `gh pr view --json files` (PR-touched only) or `git diff <merge-base>...HEAD` (three-dot, single-direction) |
| 7 | Asserting "PR modifies file X" because `git diff <base>..HEAD` lists X | Cross-check: `git log <base>..HEAD -- <file>` — if empty, PR has zero commits touching the file (the two-dot diff is showing main's later change in reverse). The finding's "regression introduced by PR" claim is false; squash merge preserves main's change because PR's change set is empty for that file |

#### Self-check (before every classification)

1. Do you have the result of `gh pr view <N> --json files` in memory?
2. Did you cross-check each finding's file path against the diff file list?
3. Did you add a **scope label** column (In diff / Outside diff) to the classification report table?
4. For items classified as deferred, did you review **In diff** items for promotion to immediate fix candidates?
5. **Two-source cross-check (HARD STOP)** — for any finding that claims "PR modified file X", verify BOTH: (a) `gh pr view --json files` lists X, AND (b) `git log <base>..HEAD -- <file>` returns 1+ commits. If (a)=yes and (b)=empty, or (a)=no and (b)=any, the finding is suspect — the file is most likely main's change PR did not absorb. The squash merge preserves main's state for files PR did not touch (commit count 0 in (b)) — "pre-merge rebase required" claims must be backed by (b) ≥ 1.

### Step 4-B: Option grouping guide (MANDATORY — before constructing Step 5/Step 8 options)

When bundling classified findings into AskUserQuestion options, the **finding-count cumulative** pattern (A only / A+B / A+B+C / all) is forbidden. Instead, generate option candidates by grouping the **Apply group** and **Deferred group** each by semantic unit.

#### Apply group (natural per commit)

| Grouping criterion | Bundling example |
|-------------------|------------------|
| **Same file** | A (App.svelte:23) + other App.svelte changes → same commit |
| **Same domain** | E (extension.ts openTerminalHere) — extension domain. If it follows the same pattern as startClaudeInFolder, commit together |
| **Same abstraction layer** | UI fix (A, B), test infra (D), core (C) — each as a separate commit is natural |
| **Sequential dependency** | C (cleanup.ts defensive guard) → D (cleanup-related test) → same commit |
| **Trivial fix bundle** | Multiple 1-line fixes bundled into one chore commit |

#### Deferred group (follow-up bundle)

| Grouping criterion | Bundling example |
|-------------------|------------------|
| **Same follow-up PR target** | B + additional web UI refactor findings → separate web-cleanup PR |
| **Same issue unit** | E (terminal mode regression) → register as separate issue |
| **Unrelated deferreds separated** | If each goes to a different follow-up, separate them in options too (standalone items, no bundling) |

#### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | Finding-count cumulative options ("A only / A+B / A+B+C / all") | Semantic group options ("UI one-liner bundle / extension domain / test infra / all") |
| 2 | Unioning findings from separate domains into one option ("A + D immediate fix") | If domains differ, separate the options, or explicitly state the reason for bundling (e.g., "for atomic verification") |
| 3 | Compressing deferreds into a single option ("D + E deferred") | If the deferred group has different follow-ups, explicitly separate follow-up medium in option description |
| 4 | Including C (Rejected) finding in apply option candidates | Rejected belongs to a separate pushback comment track. Don't bundle with apply options (apply option + separate pushback) |
| 5 | Always adding "fix all" as the last default option | If "fix all" forms a natural atomic bundle, make it the first option; otherwise exclude |

#### Self-check (before every option construction)

1. Are option candidates finding-count cumulative? → If yes, reconstruct as semantic groups
2. Do findings within each option naturally bundle into the same commit?
3. If there are deferred options, is the follow-up medium (separate PR / separate issue / checklist) natural?
4. Are Rejected findings separated from apply options? (Pushback is a separate track)
5. Does the option label make the group meaning clear at a glance? (e.g., "UI one-liner bundle" vs "fix 2 items")

#### Violation case

In the re-asked AskUserQuestion, options "A only / A+B+E / A+B+D+E / all 5" were presented. Finding-count cumulative pattern. User pointed out: "Also consider harmony between apply features and between deferred features." Resolved by adding this Step 4-B.

### Dual-label (Type | Severity, orthogonal)

Classify using **CodeRabbit-style dual-label** (category + severity combination):

> **⚠️ Two axes are orthogonal (HARD STOP)**: **Type category** (what it is) and **Severity category** (how important) are **separate classification axes**, and one finding simultaneously holds one value on each axis. You cannot "downgrade/upgrade" one axis to another. Example: "Change Important → Potential" = ❌ invalid request (Important is Severity, Potential is Type). "Downgrade Important → Minor" = ✅ movement within the same axis (Severity).

**Type category** (what it is — Category Type):

| Label | Meaning |
|-------|---------|
| ⚠️ Potential issue | Possible bug, security risk, logic error |
| 🛠️ Refactor suggestion | Refactoring, structural improvement |
| 📝 Nitpick | Naming, style, minor improvement |
| 💡 Tip | Reference info, alternative suggestion |
| ✅ Verification | Verification needed |

**Severity category** (how important — Severity):

| Label | Meaning | Action |
|-------|---------|--------|
| 🔴 Critical | Must fix — blocks merge | Fix required |
| 🟠 Important | Should fix — does not block merge | Should fix |
| 🟡 Minor | Optional fix — Nitpick level | Evaluate with user |
| 🟢 No issue | No action needed | No action |
| ⚪ Rejected | Technically inappropriate | Reject with reasoning |

**Notation format**: `Type | Severity` — e.g., `⚠️ Potential issue | 🔴 Critical`, `🛠️ Refactor | 🟠 Important`, `📝 Nitpick | 🟡 Minor`

**Orthogonal matrix example** (one finding has one value on each axis):

| Type ＼ Severity | 🔴 Critical | 🟠 Important | 🟡 Minor |
|------------------|-------------|--------------|----------|
| ⚠️ Potential | Security vulnerability (immediate fix) | Suspected 1-day blocking timezone handling | Uncovered edge case |
| 🛠️ Refactor | Missing API permission guard | Introduce helper for 29 fields | Variable name consistency |
| 📝 Nitpick | (rare) | (rare) | Missing screenshot attachment |

**Axis confusion forbidden Don't / Do**:

| # | Don't | Do |
|---|-------|-----|
| 1 | "Change Important → Potential" (different axis) | "Downgrade Important → Minor" (within Severity axis) or "Reclassify Potential → Refactor" (within Type axis) |
| 2 | In AskUserQuestion, presenting handling options bundled by only one axis label | Confirm the intent axis first, then ask: "Downgrade Severity?" vs "Reclassify Type?" |
| 3 | User says "treat as Potential" → replacing Severity Important with Potential | "Treat as Potential" is a Type change request. Or if user intent is ambiguous, use AskUserQuestion to confirm which axis |
| 4 | Changing only one axis and omitting the other axis notation | Keep both Type + Severity explicitly (e.g., `⚠️ Potential` + `🟠 Important`) |

**Self-check (whenever the user instructs a change with category/severity keywords)**:

1. Is the word the user mentioned a **Type axis** word (Potential/Refactor/Nitpick/Tip/Verification)? Or a **Severity axis** word (Critical/Important/Minor/No issue/Rejected)?
2. If neither axis has the word or it's ambiguous → use AskUserQuestion to confirm which axis the change is on
3. Changing one axis does not touch the other axis notation (e.g., when Important → Minor, Type notation `⚠️ Potential` stays unchanged)

**Severity label rule**: All review comments (Internal Code Review, AI Review Summary) use the same dual-label standard.

**Blind acceptance forbidden.** Each Actionable/Suggestion item must have a one-line verification note: what was checked and why it's valid.

Present classified results to user via text summary. **Do NOT auto-fix anything.**

### Checklist extraction guide (required)

All Actionable items (feedback requiring a fix) must be extracted as individual tasks under the corresponding PR section of the checklist. This record prevents omissions and becomes the concrete backlog for the code workflow.

- **Format**: `- [ ] [REVIEW_FEEDBACK] {reviewer name}: {issue summary} — {specific fix direction/location}`
- **Example**: `- [ ] [REVIEW_FEEDBACK] CodeRabbit: Keyboard shortcut not working — Add focus() call when MessageEditor.svelte dialog show=true`

> **Ralph (autonomous mode) exception**: AskUserQuestion is unavailable. Skip Step 5 (`decide.md`) and proceed directly to Step 7 (`post.md`) to post the Summary immediately. Record all Actionable items as `[REVIEW_FEEDBACK]` entries in the checklist per the extraction guide above, awaiting code application in the next loop.

## Next

→ `decide.md` (Step 5 User Decision + Step 6 Fix)
