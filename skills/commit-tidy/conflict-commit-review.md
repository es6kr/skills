# Conflict Commit Review

A commit whose **message carries conflict residue** — `Conflicts:`, a pasted conflict file
list, or any variation of the merge/rebase conflict template — is never eligible for the
fast paths this skill otherwise offers. It must not be squashed, reworded, reordered, or
pushed on the strength of a clean-looking tree. Its diff is reviewed **hunk by hunk, with an
explicit ask per chunk group**, before any other tidy operation touches it.

## When to Use

- Inspecting or tidying a range of commits (`squash`, `soft-reset-amend`, `interactive-amend`)
- Deciding whether a branch is safe to push
- Any time `git log` over the range shows a message matching the detection pattern below

## Why

A conflict resolution can be **syntactically clean and semantically wrong**. The resolver
picked one of two versions under time pressure; nothing in the resulting tree records that a
choice was made, and a tree with zero `<<<<<<<` markers proves only that the *markers* were
removed — not that the surviving side was the right one.

The commit message is usually the only durable signal that such a choice happened. Treating
that signal as cosmetic ("just a bad message, I'll reword it during the squash") destroys
the one breadcrumb pointing at an unreviewed decision, and the discarded side's absence
rides silently into the push.

The failure is quiet by construction: the branch builds, the file reads plausibly, and the
regression only surfaces where the dropped side was load-bearing.

## Detection

```bash
# conflict residue in commit messages across the push range
git log --oneline <base>..<branch> | grep -iE 'conflict'

# related smell: placeholder / junk messages that also mark an unreviewed commit
git log --oneline <base>..<branch> | grep -iE '^[0-9a-f]{7,} .{0,3}$|^[0-9a-f]{7,} (wip|tmp|test)$'

# rarer, separate failure: markers that survived into the tree
git grep -lE '^(<<<<<<<|=======$|>>>>>>>)' <branch>
```

A marker scan returning zero files does **not** clear a conflict commit. The two checks
answer different questions: markers detect an *abandoned* resolution, the message detects a
*completed but unreviewed* one. Only the second is common.

## Procedure

### Step 0. Scope each conflict commit before reading any diff

```bash
git branch --contains <sha>      # which local branches carry it
git branch -r --contains <sha>   # whether a remote already has it
git show --stat --format='' <sha>
```

| Result | Disposition |
|--------|-------------|
| Contained in no branch | Dangling — out of scope, no action |
| Contained only in branches outside the push set | Out of scope for this push; note it and move on |
| Already on a remote branch | Rewriting is a force-push decision — a separate ask, not part of this review |
| In the push set, local only | **Review target** — continue to Step 1 |

Scoping first avoids spending per-chunk asks on commits that cannot reach anyone.

### Step 1. Establish which side is correct by evidence, not by reading

Reading the diff tells you what changed, not which version belongs on this branch. Two
mechanical checks decide it:

```bash
# do the paths the resolution kept actually exist on this branch?
git ls-tree -r --name-only <branch> -- <path-the-resolution-kept>
git ls-tree -r --name-only <branch> -- <path-the-resolution-dropped>
```

Then run the affected tests **twice** — once against the committed state, once against the
candidate state — and record both numbers. A resolution that points at a directory absent
from this branch is wrong no matter how reasonable its diff reads.

Use a worktree for the second run rather than mutating the checkout:

```bash
git worktree add <path> <branch-carrying-the-commit>
```

### Step 2. Group hunks by trade-off, not by count

Enumerate the hunks per file:

```bash
git diff -U0 -- <file> | grep -c '^@@'
```

Then sort them by **what decision each represents**:

| Group kind | Handling |
|------------|----------|
| One side is strictly better (adds a case, adds a guard, loses nothing) | One ask for the whole group; say plainly that there is no trade-off |
| Each side carries something the other lacks (one has correctness, the other coverage) | Its own ask — this is the group that must never be decided wholesale |
| Pure formatting, no semantic delta | Fold into the nearest semantic group; do not spend an ask |

A per-file or per-hunk split that ignores this grouping produces busywork asks for
mechanical hunks while burying the one real decision among them.

### Step 3. Ask per group, and offer the merge

Wherever both sides carry value, the options must include a **merge of both sides** — not
only "take mine" / "take theirs". Taking either side wholesale is a loss the user never
asked for.

Present the merged result as a **code block** before asking, then apply it directly once
accepted. A prose summary of the resolution ("keep the guard, restore the candidate list")
is not a substitute for the text that will land in the file, and handing the user a
description to transcribe themselves turns a decision into a chore.

### Step 4. Apply, then verify with numbers

Apply the accepted resolution, re-run the affected tests, and report the delta explicitly:

```
committed state:  1 failed, 16 passed
candidate state:  15 passed
merged state:     23 passed
```

The third number is the point of the exercise. If the merge does not beat both single-side
options, the grouping in Step 2 was wrong — revisit it rather than shipping the merge.

### Step 5. Only now resume the tidy operation

Squash, reword, and reorder are safe once the resolution is reviewed and verified. Reword
the conflict message into a real one at this point — it has served its purpose.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat `Conflicts: …` as a message defect and fix it during a squash | The message is a review trigger. Review the diff first (Steps 0-4), reword last (Step 5) |
| 2 | Conclude the commit is fine because `git grep` finds no conflict markers | Markers detect abandoned resolutions only. A completed-but-wrong resolution leaves a clean tree |
| 3 | Read the diff and judge which side looks right | Decide by evidence: do the referenced paths exist on this branch, and do the tests pass on each state? |
| 4 | Accept one side of the file wholesale because it passes the tests | Passing is necessary, not sufficient — the failing side may carry coverage the passing side dropped. Compare what each side *has*, then merge |
| 5 | Split every hunk into its own ask because "chunk by chunk" was requested | Group by trade-off (Step 2). Chunk-level review means no real decision gets bundled away, not that mechanical hunks each get a turn |
| 6 | Push the branch and handle the conflict commit afterwards | The commit is inside the push range; once it is on a remote, fixing it becomes a force-push decision affecting everyone who fetched it |
| 7 | Commit the reviewed resolution without checking who else owns those files | If the affected files were already modified in the checkout before this work began, the commit carries someone else's in-flight change — see [staging-discipline.md](./staging-discipline.md) |

## Self-check (before any squash / reword / push touching the range)

1. Did I grep the range's commit messages for conflict residue, rather than assuming a clean
   `git status` means a clean history?
2. For each hit, did I scope it (Step 0) before reading its diff?
3. Did I decide the correct side from path existence and test runs, not from reading?
4. Did I record test numbers for **both** original states plus the merged state?
5. Does every trade-off group have its own ask, with a merge option offered?
6. Are the affected files free of pre-existing modifications from other work?
