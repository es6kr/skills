# Driver Interface

The normalized method contract every forge adapter must satisfy. Each method takes
forge-neutral inputs and returns a **normalized** shape, so the caller (a pipeline such as
code-workflow) consumes results without knowing which forge is behind them.

## Methods

| Method | Input | Normalized return | GitHub impl | GitLab adapter | Gitea adapter |
|--------|-------|-------------------|-------------|----------------|---------------|
| `pr_create(base, head, title, body, draft)` | branches + body | `{ref, url, number}` | `gh pr create` | `glab mr create` | `tea pr create` / API |
| `pr_view(ref, fields)` | ref + field set | `{body, checks[], mergeable, state}` | `gh pr view --json` | `glab mr view` | API `pulls/{idx}` |
| `pr_merge(ref, strategy)` | ref + `squash\|merge\|rebase` | `{merged: bool, sha}` | `gh pr merge --squash` | `glab mr merge --squash` | API `pulls/{idx}` merge |
| `pr_checks(ref)` | ref | `[{name, state, conclusion}]` | `gh pr checks` / `gh run` | `glab ci status` | commit-status API |
| `issue_create(title, body, labels)` | metadata | `{ref, url, number}` | `gh issue create` | `glab issue create` | `tea issue create` |
| `issue_edit(ref, patch)` | ref + partial update | `{ok}` | `gh issue edit` | `glab issue update` | API PATCH |
| `repo_visibility()` | — | **enum** `PUBLIC\|INTERNAL\|PRIVATE` | bool → 2 values | 3 values native | bool → 2 values |
| `auth_status()` | — | `{account, scopes[], ok}` | `gh auth status` | `glab auth` / `GITLAB_TOKEN` | `tea login` state |
| `ref_format(kind)` | `pr\|mr\|issue` | forge-specific display string | PR & issue `#N` | MR `!N`, issue `#N` | PR & issue `#N` |
| `dep_block(a, b)` | two refs | `{supported: bool, applied}` | GraphQL `addBlockedBy` | REST issue links | issue-dependencies API |
| `review_bots()` | — | capability list | `[copilot, coderabbit]` | `[coderabbit]` | `[coderabbit?]` |

## Key normalization points

- **`repo_visibility()` → 3-value enum** is the critical normalization. It makes the
  PUBLIC-vs-PRIVATE language + sanitize gates (owned by `github-flow`) forge-portable.
  GitLab's native `internal` maps to **PRIVATE** (not externally indexed), so an internal
  repo does not get PUBLIC sanitization applied. GitHub and Gitea expose only a boolean
  (public / private), which maps to the `PUBLIC` and `PRIVATE` subset of the enum.
- **`ref_format(kind)`** branches reference notation for bodies: GitHub uses bare `#N`
  autolinks, GitLab uses MR `!N` (issues stay `#N`), Gitea uses `#N`. Callers that write
  cross-references must ask the driver for the correct token rather than hardcoding `#N`.
- **`dep_block(a, b)`** returns `{supported: bool}` — the caller checks `supported` before
  relying on native dependency links and falls back to a body text reference when `false`
  (see [capability-matrix.md](./capability-matrix.md)).

## Contract completeness

The driver contract must cover every direct host-CLI call the reference implementation
makes today. Verify against `github-flow`:

```bash
grep -rn "gh \(pr\|issue\|api\|auth\)" skills/github-flow/
```

Every matched call should map to one of the methods above, or be listed explicitly as
out-of-scope (e.g., GitHub-only GraphQL operations that surface through capability flags
rather than a driver method).
