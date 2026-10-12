# Explicit Feature Base Gate

Isolation and ancestry are separate gates. A fresh worktree created from an
unrelated local HEAD can be clean while carrying extra commits. Run
`scripts/verify_feature_base.py` with a task-owned, explicit base and scope.
Never infer the base from HEAD, upstream, the current branch name or merge-base.

## Contract

Resolve the intended integration ref to a commit after the authorized freshness
check and pin that SHA for the task. Record the approved final commit count and
literal repository-relative allowed paths. A trailing `/` permits a directory
and its descendants; without it a path matches only that exact file. Empty
scope, pathspec magic, parent paths and Git failures reject, never skip.

```bash
BASE_SHA=$(git -C <source> rev-parse --verify <explicit-base-ref>^{commit})
git -C <source> worktree add -b <feature> <target> "$BASE_SHA"
python3 <git-repo-skill>/scripts/verify_feature_base.py \
  --repo <target> --base "$BASE_SHA" --mode start \
  --expected-commits 0 --allow-path <owned-file> --allow-path <owned-directory/>
```

- `start`: clean worktree, HEAD exactly equals base, zero commits.
- `stage`: verify current linear range and all changed, staged and untracked
  paths against scope. Dirt is allowed only within scope. Use the **current**
  approved count before the next commit, not the proposed post-commit count.
  This supplements, not replaces, staged-hunk intent and secret checks.
- `deliver`: clean worktree, base ancestor, exact approved final commit count,
  linear range and in-scope diff, including every commit
  (a reverted unrelated commit cannot hide in the net diff). A one-commit feature must be a direct child of
  base. Renames inspect both source and destination. Active Git operations fail.

```bash
python3 <git-repo-skill>/scripts/verify_feature_base.py \
  --repo <target> --base "$BASE_SHA" --mode stage \
  --expected-commits <current-count> --allow-path <owned-file>
# Explicit staging, audit, tests and the authorized local commit follow.
python3 <git-repo-skill>/scripts/verify_feature_base.py \
  --repo <target> --base "$BASE_SHA" --mode deliver \
  --expected-commits <approved-final-count> --allow-path <owned-file>
```

Do not use `|| true`, auto-expand scope, adjust the count to whatever Git found,
or reset/cherry-pick automatically after a rejection. Inspect and correct the
branch under the existing task authority. Re-run delivery at local handoff and
immediately before separately authorized publication. A pass is a read-only
snapshot, not an atomic lock or an always-on harness interceptor.

## Adapter boundary

Harness adapters consume this same contract. A runtime adapter may veto only
its documented supported routes; reading this topic or passing standalone tests
does not establish live enforcement. Keep source, regression, runtime load and
actual allow/block receipts separate. Generic workflow prose must not depend on
one vendor's tool names or credentials.
