# Verify (tracker reference staleness check)

Cross-checks commit-hash and file-path references cited inside `fix_plan.md` / `checklist.md` items against actual local git state, **before** trusting a "still unresolved" claim.

## When to Use

- Before triaging or acting on a `[BLOCKED]` / `[ ]` item that cites a specific commit hash or file path as evidence of an unresolved defect
- As a pre-check inside `priority` (see [priority.md](./priority.md)) triage, or standalone via `/fix-plan verify`
- When a tracker has accumulated entries across many sessions and staleness risk is high (long-lived Carryover/Hold sections)

## Why this is separate from `sync`

[sync.md](./sync.md) polls **external GitHub state** (`gh pr view` / `gh issue view`) — it answers "did the PR/issue change state on GitHub." This topic checks **local git-object and filesystem state** — it answers "does the commit this item cites actually exist, and does the file it points at still show the described problem." A tracker item can cite a commit hash that was never actually created (recorded from a plan that was never executed, or lost when a branch was reset), or point at a file that was since deleted/renamed — `sync` cannot detect either, since neither touches GitHub.

## Procedure

### 1. Extract reference tokens

Grep the tracker for two token shapes:

```bash
# Commit-hash-like tokens (7-40 hex chars, word-bounded)
grep -noE '\b[0-9a-f]{7,40}\b' <tracker-file>

# Quoted file-path references (backtick-quoted paths with a slash or a known extension)
grep -noE '`[A-Za-z0-9_./-]+\.(md|sh|py|js|ts|json|yml|yaml)`' <tracker-file>
```

Exclude obvious false positives before resolving: version strings (`v0.1.0`), dates formatted as digits, and UUIDs (36-char with hyphens — not a bare hex token).

### 2. Resolve each token against git

```bash
# Commit hash: does it exist in the repo at all (not just the current branch)?
git cat-file -e <hash> 2>/dev/null && echo "exists" || echo "PHANTOM"

# Broader existence check (unreachable/dangling objects too — a commit made once
# but never merged/pushed is still "real", just orphaned)
git rev-list --all 2>/dev/null | grep -q "^<hash>" || git fsck --unreachable --no-reflogs 2>&1 | grep -q "<hash>"

# File path: does it still exist at HEAD (or anywhere in history, if the item
# claims a past state)?
git cat-file -e "HEAD:<path>" 2>/dev/null && echo "exists at HEAD" || echo "MISSING"
```

### 3. Flag unresolvable references

For each token that fails resolution (phantom commit, missing file), flag the tracker item it came from — do not silently treat the item's "still unresolved" claim as current fact. Two outcomes are equally likely and both require checking the target's *current* state (not just the reference's existence) before acting:

| Resolution result | What it means | Next step |
|--------------------|----------------|-----------|
| Hash/path resolves, and the described defect still reproduces at that location | Item is genuinely still open | Proceed with the item normally |
| Hash/path resolves, but the described defect no longer reproduces (code already matches the fix) | Item is stale — already resolved by other work | Correct the tracker (`[x]` + one-line note), do not re-apply |
| Hash is phantom (never existed) or path is missing entirely | The reference itself is unverifiable | Surface to the user/session — do not assume either "still broken" or "already fixed"; the claim cannot be checked at all |

### 4. Report

State the count of tokens extracted, how many resolved cleanly, and how many were flagged — do not silently skip reporting the check ran.

```text
Tracker verify: N hash refs + M path refs extracted, X resolved, Y flagged (phantom/missing)
```

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Trust a tracker item's "still unresolved" wording at face value when it cites a specific commit/file | Resolve the cited commit/path against git before acting on the claim |
| 2 | Treat a phantom commit hash as "must mean the fix was never applied" | Phantom = unverifiable, not "unresolved". Check the target location's current state directly, independent of the stale reference |
| 3 | Skip this check because the tracker "looks recent" | Staleness is about the reference's accuracy, not the tracker's age — a reference can go stale within the same session if other work lands concurrently |
| 4 | Silently correct flagged items without reporting the count | Always emit the report line (Step 4) — the check's value is visible verification, not a silent pass |

## Self-check (before triaging a `[BLOCKED]`/`[ ]` item that cites a hash or path)

1. Does the item text contain a hash-like token or a backtick-quoted file path?
2. If yes, resolve it per Step 2 before treating the item's claim as current
3. Unresolvable (phantom/missing) → flag for the user, do not guess either direction
4. Resolvable but target state contradicts the claim → correct the tracker, don't re-apply
