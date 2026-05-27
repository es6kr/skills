# SSH Key

Configure per-repo `core.sshCommand` to map SSH keys for multi-account GitHub access.

## When to Use

- Multiple GitHub accounts with different SSH keys (e.g., one for personal, one for work)
- SSH agent loads keys in wrong order — `git@github.com` authenticates as the wrong account
- `Repository not found` errors despite correct SSH key existing

## Problem

When multiple SSH keys are loaded in the SSH agent, Git uses the **first matching key** regardless of `IdentitiesOnly=yes` or `-i` flag. This causes:

```
$ ssh -i ~/.ssh/<account>/<key> -o IdentitiesOnly=yes -T git@github.com
Hi other-account!  ← Wrong account! Agent key takes priority
```

## Solution

Use `core.sshCommand` with `IdentityAgent=none` to bypass the SSH agent entirely:

```bash
git config core.sshCommand "ssh -o IdentityAgent=none -i ~/.ssh/<account>/<key> -o IdentitiesOnly=yes"
```

- `IdentityAgent=none` — disables SSH agent, forces file-based key only
- `-i <key>` — specifies the exact key file
- `IdentitiesOnly=yes` — prevents SSH from trying other keys

## Procedure

### 1. Identify the SSH key mapping

Check `~/.ssh/config` for host aliases and their associated keys:

```bash
grep -A3 "Host " ~/.ssh/config | grep -E "Host |IdentityFile"
```

### 2. Verify key-to-account mapping

```bash
# Test which GitHub account each key authenticates as
ssh -o IdentityAgent=none -i <key_path> -o IdentitiesOnly=yes -T git@github.com
```

### 3. Apply to repositories

For all repos under an org directory:

```bash
for dir in ~/ghq/github.com/<org>/*/; do
  if [ -d "$dir/.git" ] || [ -f "$dir/.git" ]; then
    cd "$dir"
    git config core.sshCommand "ssh -o IdentityAgent=none -i <key_path> -o IdentitiesOnly=yes"
    echo "✅ $(basename $dir)"
  fi
done
```

### 4. Verify push works

```bash
git push --dry-run origin <branch> 2>&1 | head -3
```

Expected: `Everything up-to-date` or `rejected` (auth OK, needs fetch) — NOT `Repository not found`.

## Why Not Change Remote URL?

Changing `git@github.com` to `git@host-alias` (e.g., `work-github`) works for CLI Git but may break GUI clients like SourceGit that don't resolve `~/.ssh/config` host aliases via their internal SSH client.

`core.sshCommand` is compatible with both CLI and GUI Git clients since it's a standard Git config option.

## Notes

- This is a **per-repo** setting stored in `.git/config` — does not affect other repos
- If a repo is cloned fresh, the setting must be re-applied
- For `ghq get`, apply after clone using the patrol or clone topic
