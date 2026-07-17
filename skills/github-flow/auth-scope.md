# Auth Scope — gh CLI Priority + Account Mapping + Batch Scope Refresh + 404 Checklist

## gh CLI Priority and Browser Agent Restriction (HARD STOP)

**All GitHub operations (PR lookup, review, comment, merge, etc.) must use the `gh` CLI tool first; routing around via a browser agent is strictly forbidden.**

| # | Don't | Do |
|---|-------|----|
| 1 | Call a browser agent to check/consolidate PR reviews | Combine `gh pr view`, `gh api`, `gh pr checks`, etc. to extract data from the CLI |
| 2 | Skip the CLI based on the subjective judgment "the browser is more accurate" | The `gh` CLI maintains auth and context — it is the most reliable source. Consider the browser only when the CLI fails |
| 3 | Wait for browser rendering for simple info lookups (e.g., comment lists) | Parse JSON with `gh api`. Much faster and uses fewer tokens |

Use the browser agent **only for special situations that are genuinely impossible via the CLI** (e.g., complex GUI configuration, visual layout verification), and only with prior user approval.

## Account Mapping (per organization)

| Account | Purpose | git author identity |
|---------|---------|---------------------|
| `DrumRobot` | es6kr org repositories (es6kr/skills, claude-code-sessions, etc.) | `DrumRobot <drumrobot43@gmail.com>` |
| `<personal-account>` | Personal org / personal repositories | `<personal-account> <personal@email.com>` |

**Account switching**: `gh auth switch --user <account>`. On failure, inject `GH_TOKEN="$(gh auth token --user <account>)"` as an environment variable instead (must be passed via a script file — env vars are not preserved between separate Bash calls).

## commit author + PR account must map to repo owner (HARD STOP)

**The gh account mapping applies not only to push/PR auth but also to commit author identity.** When committing/PRing to an es6kr org repository (including PUBLIC ones), proceeding with the `gh` active account still set to a non-primary account (a residual from other work) will permanently bake the wrong author into PUBLIC history. **Switch git author identity + gh account to match the repo owner before committing.**

| # | Don't | Do |
|---|-------|----|
| 1 | Commit to an es6kr org repo while the active account is a non-primary account → wrong author baked in | Before committing: `git -C <repo> config user.name "<correct-name>" && git -C <repo> config user.email "<correct-email>"` |
| 2 | Only switch the gh account for push/PR while leaving commit author as the wrong account | author + committer + push + PR must all match the repo owner's identity. Author is permanently recorded in PUBLIC history, so they must match |
| 3 | Assume "auth is only needed at push time" | Commit author is baked in at commit time. An already-committed author can only be changed via amend/rebase |
| 4 | Commit without checking the repo owner, relying on the current git config | Right before committing, run `git remote get-url origin` to confirm the owner → apply identity per the mapping table |

**Self-check (every time before committing — based on repo owner)**:
1. `git -C <repo> remote get-url origin` → confirm owner (es6kr / `<your-org>` / `<personal-account>`)
2. es6kr org → apply the es6kr git author identity + at push/PR time: `gh auth switch --user <es6kr-account>` or `GH_TOKEN="$(gh auth token --user <es6kr-account>)"`
3. Other org/personal repos → apply the corresponding git author identity per your mapping table
4. If current `git config user.email` does not match the mapping, correct it before committing. If already committed incorrectly and **unpushed**, use `git commit --amend --reset-author` (no force push needed)
5. PR creation also uses the same mapped account (`gh pr create` uses the active account → `gh auth switch` or `GH_TOKEN` injection beforehand)

## Required gh CLI Scopes (by operation)

**On a 404 or when a scope top-up is instructed, batch-refresh all permissions listed below in one go so the user is not asked to authenticate in the browser multiple times (HARD STOP).**

| Operation | Required scope | Notes |
|-----------|---------------|-------|
| Public repository read | `repo` (or `public_repo`) | |
| Private repository (org) | `repo`, `read:org` | Required for org repositories (e.g., private GitHub orgs) |
| Create / update / merge PR | `repo` | |
| Create / update / comment on issue | `repo` | |
| Query / trigger GitHub Actions workflows | `repo`, `workflow` | For `gh run`, `gh workflow` commands |
| Create / upload release | `repo` | |
| Discussions | `repo`, `read:discussion` | |
| Codespaces | `codespace` | |
| Copilot settings | `copilot` | e.g., registering Copilot as a reviewer |
| Query user email | `user:email` | |
| Create / update Gist | `gist` | |
| Pages management | `repo`, `pages` | |

**Recommended minimum / default scope combination (batch-apply target)**: `repo,read:org,workflow,copilot`

## gh auth Permission Refresh and Top-up Rules (HARD STOP)

| # | Don't | Do |
|---|-------|----|
| 1 | On a scope top-up, only refresh `repo,read:org` and then add `copilot` separately later, forcing multiple browser authentications | As soon as a scope top-up is instructed or a missing scope is detected, batch-refresh the full set `repo,read:org,workflow,copilot` with the `-s` option in one go |
| 2 | When topping up permissions for multiple accounts sequentially, cut between accounts and repeat `switch` inefficiently | Minimize the number of `gh auth switch` invocations and browser authentication prompts — keep the design simple enough that a single-pass batch apply is possible |

```bash
# Batch-refresh all scopes including copilot
env -u GITHUB_TOKEN gh auth refresh --user <account> --scopes "repo,read:org,workflow,copilot"
```

## Org Repository 404 Checklist

Attempt the following steps in order before asking the user:

1. **Check account**: `gh auth status` → confirm the active account has permissions for the target org
2. **Check scopes**: inspect "Token scopes" in `gh auth status` output — do all required scopes from the table above appear? If not, run `gh auth refresh --user <account> --scopes "..."`
3. **GH_TOKEN env var injection workaround (most common fix)**: even after switching via `auth switch`, a known gh CLI bug prevents some commands from using the active account. Work around it with the following pattern:
   ```bash
   GH_TOKEN="$(gh auth token --user <account>)" gh repo view <org>/<repo>
   ```
   If this succeeds, scope/membership is fine — the issue is in the gh CLI itself, no user action needed
4. **Check org membership**: if all three steps above still produce 404, ask the user whether they are a member of the org
