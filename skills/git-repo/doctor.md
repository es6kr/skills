# Git Repository & Hook Doctor

Comprehensive health check and diagnosis for Git repository hooks across universal (Tier 1 Base) and context-specific (Tier 2 Conditional) standards.

## When to Use

- Repository pre-push or pre-commit checks fail unexpectedly or are bypassed
- New repository onboarding or repository hooks audit (`.githooks` vs `core.hooksPath`)
- Branch deletion wastes heavy CI resources in `pre-push`
- Staging and pushing private branches (e.g. `refs/heads/local`) needs protection
- Audit public repositories for secret/Korean text leakage or corporate repositories for direct `main` push protection
- User mentions: "repo doctor", "hook health", "diagnose hooks", "check hooks", "hook wiring", "zero-SHA pre-push", "doctor"

---

## 2-Tier Diagnostic Taxonomy

```mermaid
graph TD
    A[git-repo doctor] --> B[Tier 1: Base Universal Checks]
    A --> C[Tier 2: Conditional Checks]
    
    B --> B1[BASE-1: Hook Wiring]
    B --> B2[BASE-2: File Permissions]
    B --> B3[BASE-3: Zero-SHA Pre-push Exit]
    B --> B4[BASE-4: Local Branch Guard]
    B --> B5[BASE-5: Secret & IP Guard]
    
    C --> C1[COND-MD: Markdown Lint]
    C --> C2[COND-SKILL: Skill Frontmatter]
    C --> C3[COND-AGENT: Tracker Guard]
    C --> C4[COND-GO: Go Toolchain Lint]
    C --> C5[COND-PUBLIC: English Hangul Gate]
    C --> C6[COND-CORP: Main Branch Push Block]
```

### Tier 1: Base (Universal) Checks

| ID | Category | Target | Rule & Failure Condition |
| :--- | :--- | :--- | :--- |
| **`BASE-1`** | **Hook Wiring** | `.githooks` vs `core.hooksPath` | If `.githooks/` directory exists, `core.hooksPath` MUST point to `.githooks`. Otherwise Git reads default `.git/hooks` and `.githooks/` is completely unwired/ignored. |
| **`BASE-2`** | **Permissions** | Executable bit (`+x`) | Active hook files (`pre-commit`, `pre-push`, `commit-msg`, etc.) must have executable bits (`chmod +x`). |
| **`BASE-3`** | **Pre-push Deletion** | Zero-SHA early exit | `pre-push` hook must detect remote branch deletion (`0000000000000000000000000000000000000000` or `(delete)`) and exit `0` immediately to avoid running heavy CI tests. |
| **`BASE-4`** | **Local Branch Guard** | `local` branch push guard | `pre-push` hook must contain a guard blocking accidental push of private `refs/heads/local` stage branch to remote. |
| **`BASE-5`** | **Secret & IP Guard** | Secret / IP scan | `pre-commit` hook must scan staged files for private RFC1918 IPs (`10.x`, `192.168.x`, `172.16-31.x`) and home paths. |

### Tier 2: Conditional Checks

| ID | Trigger Condition | Category | Requirement |
| :--- | :--- | :--- | :--- |
| **`COND-MD`** | Repository contains `*.md` | **Markdown Lint** | `pre-commit` or `pre-push` must contain markdown/hangul or link reference validator. |
| **`COND-SKILL`** | Repository contains `skills/*/SKILL.md` | **Skill Frontmatter** | `pre-push` or `pre-commit` must run `lint-frontmatter.sh` or equivalent metadata validator. |
| **`COND-AGENT`** | Workspace is `.agents/` or has `fix_plan.md` | **Tracker Guard** | `pre-commit` must protect against committing untracked/dirty `fix_plan.md`. |
| **`COND-GO`** | `go.mod` is present | **Go Toolchain** | `pre-commit`/`pre-push` must run `gofmt` / `go vet` / `go test`. |
| **`COND-PUBLIC`** | Remote is public (`es6kr/*`) | **Public English Gate** | `pre-commit` must contain `check-hangul` gate to enforce English-only text. |
| **`COND-CORP`** | Remote is corporate (`daegunsoftDev/*`) | **Corp Main Block** | `pre-push` must block direct push to `main` / `master` branches. |

---

## CLI Usage

### Basic Execution

```bash
# Run doctor on current repository
bash skills/git-repo/scripts/git-repo-doctor.sh

# Run doctor on a specific repository path
bash skills/git-repo/scripts/git-repo-doctor.sh /path/to/repo

# Output machine-readable JSON format
bash skills/git-repo/scripts/git-repo-doctor.sh . --json
```

### Sample Output

```text
========================================================================
  Git Repository & Hook Doctor: /path/to/repo
========================================================================
ID         TIER         CATEGORY               STATUS   DETAILS
------------------------------------------------------------------------
BASE-1     Base         Hook Wiring            PASS  core.hooksPath correctly wired to '.githooks'.
BASE-2     Base         Permissions            PASS  All active hook files have executable permissions.
BASE-3     Base         Pre-push Deletion      FAIL  pre-push hook lacks zero-SHA (40 zeros) branch deletion early exit.
BASE-4     Base         Local Branch Guard     PASS  pre-push hook contains 'local' stage-branch push guard.
BASE-5     Base         Secret & IP Guard      PASS  pre-commit hook contains secret / IP / path protection guard.
COND-MD    Conditional  Markdown Lint          PASS  Markdown files present and validated by hook.
COND-SKILL Conditional  Skill Frontmatter Lint PASS  Skill files present and verified by metadata/frontmatter lint hook.
COND-PUBLIC Conditional Public English Gate    PASS  Public English repository contains check-hangul gate in pre-commit.
------------------------------------------------------------------------
Summary: 7 Passed | 0 Warnings | 1 Failed

❌ Doctor found 1 issue(s). Follow details above to resolve.
```

---

## Remediation Runbook

### 1. Fixing Unwired `.githooks` (`BASE-1`)

If `.githooks/` directory exists but Git ignores it:

```bash
git config core.hooksPath .githooks
```

### 2. Fixing Hook Permissions (`BASE-2`)

```bash
chmod +x .githooks/*
```

### 3. Adding Zero-SHA Early Exit (`BASE-3`)

In `.githooks/pre-push`, insert the zero-SHA check at the start of the stdin reading loop:

```sh
while IFS=' ' read -r local_ref local_sha remote_ref remote_sha; do
  # Skip branch deletions immediately (prevents running heavy CI tests on branch deletion)
  if [ "$local_sha" = "0000000000000000000000000000000000000000" ] || [ "$local_sha" = "(delete)" ]; then
    exit 0
  fi

  # Branch guards & downstream checks...
done
```

### 4. Adding `local` Branch Push Guard (`BASE-4`)

In `.githooks/pre-push`:

```sh
if [ "$local_ref" = "refs/heads/local" ] || [ "$remote_ref" = "refs/heads/local" ]; then
  if [ "${PUSH_LOCAL_OVERRIDE:-}" != "1" ]; then
    echo "❌ ERROR: Pushing 'local' stage branch to remote is blocked." >&2
    exit 1
  fi
fi
```

### 5. Adding Skill Frontmatter & Language Lint (`COND-SKILL`, `COND-PUBLIC`)

In `.githooks/pre-push`:

```sh
# Verify SKILL.md frontmatter and dependencies
if [ -f "scripts/lint-frontmatter.sh" ]; then
  echo "Checking SKILL.md frontmatter..."
  bash scripts/lint-frontmatter.sh
fi
```
