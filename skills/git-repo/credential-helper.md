# Credential Helper (HTTPS multi-account)

Pin a per-org GitHub token for HTTPS remotes so the **active `gh` account** never decides which credential a private-org repo gets. The HTTPS counterpart to the SSH-focused `ssh-key` topic.

## When to Use

- Multiple GitHub accounts authenticated in `gh` (`gh auth status` shows 2+ accounts)
- A private org repo intermittently fails with `remote: Repository not found` over **HTTPS** — typically right after working on a different org whose account became active
- The failure "fixes itself" when you switch `gh` accounts, then returns later
- SourceGit / other GUI clients hit the same `Repository not found` because they call git's HTTPS credential pipeline directly

If the remote is SSH (`git@github.com:...`), use the `ssh-key` topic instead.

## Root Cause

When the global gitconfig routes GitHub HTTPS auth through `gh`:

```
[credential "https://github.com"]
    helper = !gh auth git-credential
```

`gh auth git-credential` returns the token of the **currently active** `gh` account. If the active account lacks access to a private repo, GitHub returns `404` for the repo, which git surfaces as:

```
remote: Repository not found.
fatal: repository 'https://github.com/<org>/<repo>.git/' not found
```

The repo exists and the *correct* account has access — but the *active* account doesn't, so it reads as "not found" (GitHub returns 404, not 403, for private repos you can't see). Because the active account flips as you move between orgs, the breakage is recurring rather than permanent.

| # | Don't | Do |
|---|-------|-----|
| 1 | Read `Repository not found` as "the repo was deleted/renamed" | Verify existence + access with the right account first (`gh repo view <org>/<repo> --json isPrivate`) before assuming the repo is gone |
| 2 | Fix it by `gh auth switch` each time | Switching is temporary — it breaks again when the active account flips. Pin the account per-org (Solution below) |
| 3 | Assume the credential helper is `manager`/GCM because `git config credential.helper` says so | A path-specific `credential.https://github.com.helper` overrides the generic helper. Check `git config --global --get-regexp 'credential.*github'` for the helper that actually runs |

## Diagnosis

```bash
REPO=<path-to-repo>

# 1. Which gh accounts exist, and which is active?
gh auth status

# 2. Reproduce the failure on the actual auth path (no interactive prompt)
GIT_TERMINAL_PROMPT=0 git -C "$REPO" ls-remote origin -h 2>&1 | head -3
#    → "remote: Repository not found." confirms the active-account mismatch

# 3. Confirm the repo exists + which account has access
gh auth switch --user <account-with-access>
gh repo view <org>/<repo> --json name,isPrivate     # succeeds → access OK
GIT_TERMINAL_PROMPT=0 git -C "$REPO" ls-remote origin -h ; echo "exit=$?"   # exit=0 → access OK

# 4. Inspect the helper that actually runs for github.com
git config --global --get-regexp 'credential.*github'
```

If step 2 fails with the active account but step 3 succeeds after switching, the diagnosis is confirmed: **HTTPS auth is bound to the active account**.

## Solution — org-scoped credential helper

Add a credential helper **scoped to the org path** that always emits the correct account's token, independent of the active `gh` account:

```bash
# Back up first (gitconfig is a user file)
cp ~/.gitconfig ~/.gitconfig.bak

# Empty value resets inherited helpers for this path, then add the pinned one
git config --global credential.https://github.com/<org>.helper ""
git config --global --add credential.https://github.com/<org>.helper \
  '!f() { echo username=<account>; echo "password=$(gh auth token --user <account>)"; }; f'
```

Resulting config block:

```
[credential "https://github.com/<org>"]
    helper =
    helper = !f() { echo username=<account>; echo "password=$(gh auth token --user <account>)"; }; f
```

How it works:

- `credential.https://github.com/<org>` matches only URLs under that org → other orgs are untouched
- The empty `helper =` **resets** the helper list accumulated from the broader `https://github.com` scope, so the generic active-account helper is not also consulted for this org
- `gh auth token --user <account>` returns that specific account's token regardless of which account is active
- Works for git CLI **and** GUI clients (SourceGit etc.), since they all call git's HTTPS credential pipeline

| # | Don't | Do |
|---|-------|-----|
| 1 | Set it per-repo (`git config` without `--global`) and re-do it on every clone | Scope to the org path in global config — every current and future repo under `<org>` inherits it |
| 2 | Omit the empty `helper =` reset | Without the reset, both the pinned helper and the generic active-account helper run; the active-account one can still win and re-break auth |
| 3 | Hardcode the token into the helper | Use `gh auth token --user <account>` so the token rotates with `gh` and is never written to disk |
| 4 | Edit `~/.gitconfig` blind | `cp ~/.gitconfig ~/.gitconfig.bak` first — it is a user-owned file |

## Verification (HARD STOP — GUI client too)

CLI passing alone is insufficient. The recurring failure was originally reported in a GUI client, so verify there.

```bash
# CLI: with the WRONG account still active, the org repo must now succeed
gh auth switch --user <other-account>          # simulate the breaking condition
GIT_TERMINAL_PROMPT=0 git -C "$REPO" ls-remote origin -h ; echo "exit=$?"   # expect exit=0

# Regression: a repo under a DIFFERENT org must still use its own account
GIT_TERMINAL_PROMPT=0 git -C <other-org-repo> ls-remote origin -h >/dev/null 2>&1 && echo "no regression"
```

| Verification | Action |
|--------------|--------|
| CLI (active = wrong account) | `git ls-remote origin` from the repo → exit 0, no `Repository not found` |
| Other-org regression | `git ls-remote` on a repo under a different org → still succeeds with its own account |
| **SourceGit** | Open the repo → **Fetch** → must succeed without `Repository not found` |
| Other GUI (GitHub Desktop, etc.) | Fetch origin → confirm success |

**Do not declare "fix complete" until the user's GUI client (the one that reported the failure) succeeds.** CLI green + GUI red = same root issue still active.

## Notes

- Global org-scoped config covers all repos under `<org>` — no per-clone re-application (unlike per-repo SSH `core.sshCommand`)
- This is HTTPS-only. For SSH remotes with the same multi-account problem, see the `ssh-key` topic
- The org → account mapping is the user's to decide; this topic only pins whatever mapping is given
- `gh auth token --user <account>` requires that account to be logged in (`gh auth login`) at least once
