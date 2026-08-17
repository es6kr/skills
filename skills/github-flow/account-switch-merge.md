# Account-Switch Merge (`account-switch-merge`)

Use this topic when performing a PR merge requiring a specific merger account (e.g., `DrumRobot` bot account for CI/release isolation or protected branch policies) with automatic post-merge account restoration.

## Purpose

Automates the manual 6-condition check, temporary `gh auth` user switch, squash/merge execution, and guaranteed restoration of the developer's original GitHub account state.

---

## 6 Pre-Merge Conditions Checklist (MANDATORY)

Before initiating an account switch or executing `gh pr merge`, ALL 6 conditions MUST be verified and pass:

1. **CI Success**: `gh pr checks <N>` returned all `SUCCESS` (no pending, no failed).
2. **AI Review Summary Posted**: `/consolidate pr <N>` has completed and the AI Review Summary comment is present (or PR is consolidate-exempt).
3. **Test Plan Checked**: All `- [ ]` checklist items in the PR body are marked completed (`- [x]`).
4. **Mergeable Status**: `gh pr view <N> --json mergeable` returns `"MERGEABLE"`.
5. **Base Branch Alignment**: PR is up to date with the latest base branch (no merge conflicts).
6. **Pre-Commit / Pre-Push Sanity**: Working tree is clean or changes are safely stashed.

---

## Automated 5-Step Account-Switch & Merge Protocol

### Step 1: Pre-Merge Verification
```bash
# Verify 6 pre-merge conditions
gh pr view <PR_NUMBER> --json state,mergeable,reviews,checks,body
```

### Step 2: Record Current Active User
```bash
ORIGINAL_USER=$(gh api user --jq .login)
echo "Current active GH user: $ORIGINAL_USER"
```

### Step 3: Switch to Target Merger Account
If `$ORIGINAL_USER` is not the target merger account (e.g. `DrumRobot`), switch to it:
```bash
TARGET_USER="DrumRobot"
if [ "$ORIGINAL_USER" != "$TARGET_USER" ]; then
  gh auth switch -u "$TARGET_USER"
fi
```

### Step 4: Execute Squash & Merge
```bash
gh pr merge <PR_NUMBER> --squash --delete-branch
```

### Step 5: Guaranteed Original Account Restoration (HARD STOP)
Regardless of merge success or failure, ALWAYS restore the original user account immediately:
```bash
if [ "$ORIGINAL_USER" != "$TARGET_USER" ]; then
  gh auth switch -u "$ORIGINAL_USER"
fi
```
Verify restored identity:
```bash
gh api user --jq .login
```

---

## Don't / Do Table

| # | Don't | Do |
|---|-------|----|
| 1 | Merge without checking all 6 pre-merge conditions | Verify CI, Review, Test Plan, and Mergeable status BEFORE switching account |
| 2 | Leave active `gh auth` as `DrumRobot` after merge | ALWAYS restore `$ORIGINAL_USER` in Step 5 immediately after merge |
| 3 | Use direct `git push origin main` bypass | Always merge via `gh pr merge <N> --squash` |
