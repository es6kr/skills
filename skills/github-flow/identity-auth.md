# Identity and Auth

`gh` CLI is the first-choice GitHub interface. Owner-based commit-author identity mapping. `gh auth refresh` scope management. `GH_TOKEN` env fallback for org-repo 404.

## When to use

- Before every commit on a repo whose remote owner you have not verified this session
- Before every PR creation / push that requires push authorization
- On 404 / 403 from `gh repo view`, `gh issue create`, `gh pr create`, etc.
- When switching between multiple `gh auth` accounts (multi-account workflows)
- When invoking `gh run`, `gh workflow`, `gh release`, `gh copilot` and getting a scope error

## gh CLI first (HARD STOP)

**For ALL GitHub-related work (PR view, review, comment, merge, etc.), `gh` CLI is the first-choice tool.** Forbid escape-to-browser-agent (`browser_subagent`) for routine GitHub tasks.

| # | Don't | Do |
|---|-------|-----|
| 1 | Invoke a browser agent to verify / consolidate PR review | Combine `gh pr view`, `gh api`, `gh pr checks` to extract data from CLI |
| 2 | Skip CLI on the subjective belief "the browser is more accurate" | `gh` CLI is the most reliable source — authentication and context are preserved. Consider the browser ONLY when CLI fails |
| 3 | Wait for browser-rendering of a simple data query (e.g., comment list) | `gh api` with JSON parse. Much faster, fewer tokens |

The browser agent is reserved for **situations CLI cannot handle** (e.g., complex GUI configuration, visual layout verification), with user pre-approval.

## Owner-based commit-author identity mapping (HARD STOP)

**`gh` account mapping applies not only to push / PR auth but also to commit-author identity.** When committing to an org repo (PUBLIC included), if the `gh` active account is a different identity (e.g., leftover from a different repo's work), the commit author gets stamped wrong and the wrong identity becomes permanent in PUBLIC history.

**Before commit: switch `git author identity` + `gh account` to match the repo owner.**

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Commit to an org repo with the active account left from a previous workflow → wrong author stamped | Before commit: `git -C <repo> config user.name "<name-for-owner>" && git -C <repo> config user.email "<email-for-owner>"` |
| 2 | Push / PR uses the right identity but commit author left unchanged | Author + committer + push + PR all use the same identity. PUBLIC history permanently records the author, so consistency is mandatory |
| 3 | "Auth is needed only at push time" reasoning | Commit author is stamped at commit time. An already-wrong author can only be fixed via amend / rebase |
| 4 | Commit without checking the repo owner | Right before commit, run `git remote get-url origin` to confirm the owner → set identity per the owner-identity mapping |

### Self-check (every time before commit — owner-based)

1. `git -C <repo> remote get-url origin` — determine the owner
2. Look up the owner in your **owner-identity mapping table** (workspace-specific; live in `~/.agents/.claude/rules/identity.md` or a workspace `.claude/rules/identity.md`, NOT in this generic skill)
3. Set `git config user.name` + `user.email` + `gh auth switch` (or inject `GH_TOKEN`) to match the owner mapping
4. If `git config user.email` does not match the mapping, fix BEFORE commit. If already committed wrong AND **unpushed**: `git commit --amend --reset-author` (no force-push needed)
5. PR creation also uses the matched account (`gh pr create` consumes the active account → pre-switch via `gh auth switch` or inject `GH_TOKEN`)

### Owner-identity mapping (defined elsewhere)

The actual `<owner> → <git author identity>` + `<gh account>` mapping table is **workspace-scoped**, not part of this skill. Maintain it in `~/.agents/.claude/rules/identity.md` (per-user) or `<workspace>/.claude/rules/identity.md` (per-project). Example shape (the specifics belong elsewhere):

```text
| Owner           | git author identity                   | gh account     |
| --------------- | ------------------------------------- | -------------- |
| org-A           | Identity-for-org-A <email-A@host>     | gh-account-A   |
| org-B           | Identity-for-org-B <email-B@host>     | gh-account-B   |
```

### Failure pattern

See failed-attempts.md HOT entry "PUBLIC repo commit with leftover account identity" — a PUBLIC-repo commit landed with the previous workspace's account as author. Caught while still unpushed and corrected via `git commit --amend --reset-author`.

## `gh` CLI scope (by task)

### Common scope cheat sheet

| Task | Required scopes | Note |
|------|----------------|------|
| Read public repo | `repo` (or `public_repo`) | |
| Private repo (org) | `repo`, `read:org` | Required for org-owned private repos |
| PR create / edit / merge | `repo` | |
| Issue create / edit / comment | `repo` | |
| GitHub Actions workflow query / dispatch | `repo`, `workflow` | `gh run`, `gh workflow` |
| Release create / upload | `repo` | |
| Discussions | `repo`, `read:discussion` | |
| Codespaces | `codespace` | |
| Copilot config (e.g., reviewer add) | `copilot` | |
| User email read | `user:email` | |
| Gist create / edit | `gist` | |
| Pages management | `repo`, `pages` | |

**Recommended combined scope (Ralph / autonomous workflows)**: `repo,read:org,workflow,copilot`

### Permission-grant batching rule (HARD STOP)

**On 404 detection or any "scope insufficient" instruction, refresh the FULL recommended scope set in ONE `-s`-flag call. Forbid splitting into multiple browser auth prompts.**

| # | Don't | Do |
|---|-------|-----|
| 1 | Refresh only `repo,read:org` first, then later refresh `copilot` separately → user opens browser twice | On the first scope-shortage detection, refresh the **entire** recommended scope set with a single `--scopes "repo,read:org,workflow,copilot"` call |
| 2 | Multi-account scope refresh done one account at a time with inefficient `switch` repetition | Minimize the number of `gh auth switch` + browser auth-window openings via a streamlined design that supports one-click bulk apply |

```bash
# Refresh including copilot in a single call
env -u GITHUB_TOKEN gh auth refresh --user <account> --scopes "repo,read:org,workflow,copilot"
```

## Org-repo 404 troubleshooting (self-resolve in order)

Run these in order BEFORE asking the user:

1. **Account switch check**: `gh auth status` → confirm the active account has access to the org
2. **Scope check**: `gh auth status` output's "Token scopes" — verify against the table above. If missing scope → `gh auth refresh --user <account> --scopes "..."`
3. **`GH_TOKEN` env injection (most frequent fix)**: even after `gh auth switch`, some commands fail to honor the active account due to a known gh CLI bug. Use this pattern to bypass:

   ```bash
   GH_TOKEN="$(gh auth token --user <account>)" gh repo view <org>/<repo>
   ```

   If this succeeds, your scope / membership is fine — it was a gh CLI internal issue, no user intervention needed.
4. **Org membership confirmation**: if steps 1-3 all fail with 404, ask the user about membership status

## Self-check (before any gh-auth-requiring command)

1. Is the target an org repo? — `gh repo view <org>/<repo> --json owner -q '.owner.login'`
2. If org → confirm the active `gh auth status` user has access
3. If 404 → run the troubleshooting list above (steps 1 through 4) before asking the user
4. About to refresh scopes? → use the **single** combined scope refresh (don't split into multiple browser prompts)

## Related topics

- `merge` — merge requires `repo` scope for write operations
- `pr` — PR creation requires `repo` scope; check `dependencies` for `addBlockedBy` GraphQL mutations
- `push-guards` — `gh run list` (used in force-push CI status check) requires `repo`, `workflow` scope
