# Sanitize

Pre-publish validation for any text destined for a GitHub repository (issue body, PR body, comments). Two concerns: **personal-data leak** (PUBLIC repos — permanently indexed once leaked; even `gh issue edit` leaves the original in edit history) and **internal artifact paths** (PUBLIC *and* PRIVATE — `.ralph/`/`.omc/` render as dead links in any GitHub medium).

## When to Use

- Before `gh issue create`, `gh issue edit`, `gh pr create`, `gh pr edit`, `gh issue comment`, `gh pr comment` — **PUBLIC and PRIVATE** (the internal-artifact-path scan runs for PRIVATE too; personal-data scan is PUBLIC-only)
- Inside `plan-to-issue` (Step 5.5), `pr` (body assembly), `review` (review comment), `merge` (squash commit message)
- Whenever an issue-draft from `.ralph/issue-drafts/` is being posted

## Two distinct concerns — different visibility scopes

| Concern | What | Visibility scope |
|---------|------|------------------|
| **Personal-data leak** | Session UUIDs, user home paths, external tool names, internal hostnames, metrics from user data | **PUBLIC repo only** (permanently indexed once leaked) |
| **Internal artifact paths** | `.ralph/`, `.omc/`, `~/.claude/` workflow-generated paths (links, `Artifacts` / equivalent localized sections, doc references) | **EVERY repo — PUBLIC and PRIVATE** (dead-links / noise in any GitHub medium, not a leak concern) |

The internal-artifact-path scan is **not** a personal-data concern — those paths are meaningless dead references in any PR/issue/comment regardless of visibility. Do NOT skip it for PRIVATE repos.

## Repository visibility check (always first)

```bash
gh repo view --json isPrivate -q '.isPrivate'
```

- `true` → PRIVATE repo. Personal-data sanitization not enforced (still recommended for shared repos). **Internal-artifact-path scan STILL mandatory** (see below).
- `false` → PUBLIC repo. **Both personal-data sanitization AND internal-artifact-path scan are mandatory.**

## Internal artifact path scan (HARD STOP — runs for PRIVATE repos too)

Workflow-generated paths leak into PR/issue bodies via `Artifacts` (or equivalent localized) sections, supporting-analysis links, and copied research/plan references. They render as **dead links** on GitHub (the path exists only in the local workspace). Run this scan **regardless of repo visibility**, on every `gh ... create/edit/comment`:

```bash
BODY="$(cat /path/to/body.md)"  # or whatever holds the prepared body
# Matches bare (.ralph/...), relative (../../x/.ralph/...), and tilde (~/.ralph) forms
echo "$BODY" | grep -nE '(^|[^A-Za-z0-9_.-])(\.\./)*\.(ralph|omc)/|~/\.(claude|ralph|omc)/|\.claude/(skills|plugins|hooks|projects)/' && echo "BLOCKED: internal artifact path"
```

On match → **abort the post**, remove the offending link/section (or inline the substantive content), re-scan. An `## Artifacts` (or equivalent localized) section that only lists `.ralph/docs/generated/*.md` files must be **removed entirely** — the content belongs in the body prose, not as a path reference.

| # | Don't | Do |
|---|-------|-----|
| 1 | Skip the internal-path scan because the repo is PRIVATE | Internal paths are dead-links in ANY repo. Scan PRIVATE too |
| 2 | Rely on the `~/`-anchored personal-data grep to catch `.ralph/` | That pattern misses bare (`.ralph/docs/`) and relative (`../../x/.ralph/`) forms. Use the dedicated internal-path grep above |
| 3 | Keep an `Artifacts` (or equivalent localized) section listing `.ralph/docs/generated/*.md` | Remove the section; fold any needed substance into body prose |
| 4 | Link a workspace analysis doc via relative path (`[doc](../../x/.ralph/...)`) | Drop the link; inline the analysis conclusion as text |

## Forbidden patterns (HARD STOP — abort posting if any match)

| Category | Pattern | Example | Replace with |
|----------|---------|---------|--------------|
| Session/resource UUID v4 | `[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}` | `<uuid-v4>` | `session-id`, `abc-1234-...` |
| User home path | `/Users/<name>/`, `/home/<name>/` | `/Users/<name>/<sync-folder>/...` | `~/`, `<user-home>/`, `/path/to/...` |
| Internal working paths | `~/.claude/`, `~/.ralph/`, `~/.omc/` | `~/.ralph/issue-drafts/foo.md` | Remove or generalize |
| External tooling (unrelated to the issue) | file-sync daemon, dotfile manager, version manager, identity provider, automation server, secrets store, journal app, git GUI, cloud account, edge CDN | "file-sync daemon `.sync-conflict` resolution" | "file synchronization tool" or remove |
| Internal hostnames/IPs | `<private-IP>`, `<internal-host>`, `<internal-domain>` | `<private-IP>` | "internal server" or remove |
| Metrics extracted from user data | "N lines, M unique UUIDs" | "1000+ duplicates in my session" | "hundreds or thousands of records" |
| Real file names from user data | `<uuid>.jsonl` | The user's actual session file | "test fixture file" |
| First-person environmental anecdotes | "in my environment", "across my cwd's" | Real workflow description | Generic scenario phrasing |

## Sanitization scan command

The **internal-artifact-path scan** (see section above) runs for **every** repo, including PRIVATE — run it first. The four `grep` checks below are the **PUBLIC-only personal-data** scans. On a PUBLIC repo, run all (internal-path + the four below + Hangul). Each must produce **no output** (exit code 1):

```bash
BODY="$(cat /tmp/issue-body.md)"  # or whatever holds the prepared body

# (0) Internal artifact paths — RUN FOR PRIVATE TOO (visibility-agnostic)
echo "$BODY" | grep -nE '(^|[^A-Za-z0-9_.-])(\.\./)*\.(ralph|omc)/|~/\.(claude|ralph|omc)/|\.claude/(skills|plugins|hooks|projects)/' && echo "BLOCKED: internal artifact path"

# (1)-(4) PUBLIC-repo personal-data scans
echo "$BODY" | grep -P '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}' && echo "BLOCKED: UUID detected"
echo "$BODY" | grep -E '/Users/[a-z]+|/home/[a-z]+|~/.claude|~/.ralph|~/.omc' && echo "BLOCKED: user/internal path"
echo "$BODY" | grep -iE "${PII_TOOL_KEYWORDS:-<tool-keyword-set>}" && echo "BLOCKED: external tool name"
echo "$BODY" | grep -E "${PII_INTERNAL_HOST_RE:-<internal-host-prefix>}" && echo "BLOCKED: internal hostname/IP"
```

Also run the **Korean character scan** (PUBLIC repo English-only rule):

```bash
echo "$BODY" | grep -P '\p{Hangul}' && echo "BLOCKED: Hangul detected"
```

## HARD STOP behavior

When any scan matches:

1. **Abort** the `gh ... create/edit/comment` call immediately.
2. **Report** to fix_plan: `BLOCKED: <category> found in PUBLIC repo content (<line snippet>)`.
3. **Rewrite** the offending lines in the source draft (issue-draft or working buffer).
4. **Re-scan**. Only proceed when all six scans return zero matches (internal-artifact-path + four personal-data + Hangul).

Do **not** "translate-as-you-write" or "sanitize while typing" — produce a fully cleaned draft first, scan, then post.

## Editing an existing PR body — re-validate the Test Plan category invariant (HARD STOP)

Sanitizing a PR body is a **body mutation**. Before re-posting, if the body contains a `## Test Plan` section, re-run the **Test Plan category self-check** ([pr.md](./pr.md) "Test Plan category classification"). A pre-existing flat (uncategorized) Test Plan must be prefixed now — do not preserve legacy flat items verbatim just because the edit's purpose was path-stripping.

```bash
# Flag any Test Plan item lacking a category prefix (**[general]** / **[UI]** / **[e2e]** / **[post-merge]**)
echo "$BODY" | grep -nE '^- \[.\] ' | grep -vE '\*\*\[(general|UI|e2e|post-merge|deploy)\]\*\*' && echo "WARN: uncategorized Test Plan item — apply prefixes before re-posting"
```

The category invariant holds across the body's lifetime, not just at creation. Any flow that edits a body (sanitize, review-apply, milestone, label) inherits this re-validation.

## Origin of personal data in drafts

Personal data typically enters `.ralph/issue-drafts/*.md` because:

- The user pasted real debugging output (real session file) into the draft as evidence
- Ralph wrote down "what I observed in my session" verbatim while researching
- A copied-from-elsewhere example contained another project's identifiers

**Drafts are allowed to contain debugging notes**, but the **publish step must sanitize**. Generalize the bug scenario: "construct a fixture .jsonl with intentionally duplicated lines" instead of "session `<uuid>` has N lines".

## Post-publish discovery

If personal data is discovered **after** `gh issue create/edit`:

1. Immediately `gh issue edit <N> --body "<sanitized>"` to overwrite — do not delay.
2. Note in fix_plan: GitHub `edit history` is permanent; the leak is recorded even after edit. Consider whether the exposure level warrants further action (GitHub Support request, etc.).
3. Update the source `.ralph/issue-drafts/*.md` to the sanitized version so re-publishing won't regress.

## Ralph autonomous mode

Same rule applies in autonomous loops. No `--no-confirm` or speed-pressure exemption. The four `grep` scans are non-negotiable.

## Reference

Linked from:

- `plan-to-issue.md` Step 5.5
- `pr.md` body assembly step
- `review.md` review comment posting step
- `merge.md` squash commit message preparation
- `~/.agents/rules/opensource.md` "PUBLIC repository personal data ban"
- Ralph `PROMPT.md.template` and project-local `.ralph/PROMPT.md` inline rule

Recorded violation pattern: a PUBLIC-repo issue contained user session UUIDs, raw metrics, and an external tool name verbatim — required sanitization after the fact.

## PRIVATE repo = Korean default (HARD STOP)

**`isPrivate: true` repositories: write issue title/body, PR title/body, comments, and commit messages in Korean by default.** This is the explicit inverse of the PUBLIC-English rule.

| # | Don't | Do |
|---|-------|----|
| 1 | Write a PRIVATE repo PR title/body in English (following the commit message) | Write PR title and body in Korean. Even if the commit message is English, the PR title is separately Korean |
| 2 | "Commit message is English, so PR title is naturally English too" reasoning | Per-medium language separation. Commit message follows git convention; PR title follows visibility rule |
| 3 | Skip the visibility + language mapping self-check before `gh pr create --title "..."` | Run `gh repo view --json isPrivate` every time → apply the mapping table |
| 4 | Decide the project uses an English convention and write PRIVATE PRs in English | Only write in English when the project's CLAUDE.md explicitly states an English PR convention |

**Exceptions**: project CLAUDE.md/README explicitly requires English PRs; foreign collaborator/OSS contributor is involved (that PR/issue only); user explicitly instructs "in English".

## Visibility 1st-source check before security decisions (HARD STOP)

**Before applying or skipping any security rule (PUBLIC personal data ban / secret scan / IP exposure ban), confirm repo visibility with `gh repo view --json isPrivate` as a 1st-source check every time.** No inference or assumption.

| # | Don't | Do |
|---|-------|----|
| 1 | Auto-assume "this repo is PUBLIC" and report IP/secret hardcoding as inappropriate (without checking) | `gh repo view <owner>/<repo> --json isPrivate -q '.isPrivate'` → apply/skip rules based on `true`/`false` |
| 2 | "Was PUBLIC in a previous context/session, so must still be PUBLIC" assumption | Visibility can change (PUBLIC ↔ PRIVATE). Confirm before every security decision |
| 3 | Apply PUBLIC rules to PRIVATE repos because of "GitHub exposure risk" general reasoning | PRIVATE = this section not enforced. IP/secret commits are allowed (though user/team policy may differ) |
| 4 | Infer visibility from repo name pattern (e.g., a "…-web" app repo) or from the owner org name | Naming patterns don't guarantee visibility. Always use `gh repo view` |

## Cross-repo linkage direction: private→public OK, public→private FORBIDDEN (HARD STOP)

**Referencing a PUBLIC repo from a PRIVATE repo commit/PR/issue/comment is allowed. The reverse direction (referencing a PRIVATE repo from a PUBLIC repo commit/PR/issue/comment) is forbidden.** PUBLIC repo content is permanently recorded by GitHub + external indexes (Google, Wayback Machine), permanently exposing the private repo's existence, name, and issue numbers.

| # | Don't | Do |
|---|-------|----|
| 1 | PUBLIC repo PR/commit body: `Closes private-org/private-repo#N` / `Relates to private-repo#N` | Tracking on the PRIVATE side only. PUBLIC PR body has only generic description (no PRIVATE issue mention) |
| 2 | PUBLIC repo issue comment quoting a PRIVATE repo URL or name | PRIVATE side comment citing the PUBLIC PR URL (reverse direction). PUBLIC side references only itself |
| 3 | "es6kr org is all ours, so cross-links are fine" assumption | PRIVATE = visibility=private. Outsiders can see PUBLIC repos — PRIVATE names exposed there = information leak. Same org ≠ visibility can be ignored |
| 4 | PUBLIC repo commit message footer: `tracking: private-org/.tracking#1` | No tracking info in commit messages. Tracking is done from the PRIVATE side citing PUBLIC PR URLs (one-directional but sufficient) |

### Self-check (before writing any commit/PR/issue/comment on a PUBLIC repo)

1. Confirm target repo visibility: `gh repo view --json isPrivate -q '.isPrivate'`
2. If `false` (PUBLIC), grep the body for PRIVATE references — abort + sanitize on any match:
   ```bash
   grep -E '<private-org>/<private-repo>|<private-org>\.[a-z]+|private-org-internal' <body>
   ```
3. PRIVATE repo name / issue number / PR number matched → remove from body or generalize ("internal tracking")
4. Only post after sanitize + re-scan passes

## Issue/PR Body Local-path and Internal Host Sanitize (HARD STOP — visibility-agnostic)

**PRIVATE/PUBLIC regardless, in any repo with at least 1 external contributor: local workspace paths, internal hosts, and internal tool paths are forbidden in issue/PR/comment bodies.** Even PRIVATE issue bodies are visible to all collaborators → materials only the user can access (`.claude/rules/...`, `~/.claude/skills/...`, fix_plan.md etc.) are dead references + information leaks.

| # | Don't | Do |
|---|-------|----|
| 1 | Issue body "## References" section cites `<workspace>/.claude/rules/<rule>.md` or `~/.claude/skills/...` | **Inline summarize** the rule content in the issue body (self-contained, no external reference). Rule file paths inside the same repo are OK (e.g., `.github/workflows/...`) |
| 2 | Copy "Related rule: `<path>`" / "Reference: `<path>`" pattern verbatim from fix_plan to issue body | fix_plan.md ↔ issue body medium separation. fix_plan is user-only working file; issue body is visible to collaborators |
| 3 | Cite internal RFC1918 IPs (`10.0.0.x`, `192.168.x.x`, `172.16-31.x.x`) or internal hosts (`<internal-app-server>`, `<internal-host-prefix>.*`) | Generalize ("internal Semaphore server") or env var placeholder (`$SEMAPHORE_URL`). If reproducibility needed, separate PRIVATE document |
| 4 | Assume "PRIVATE so safe" and skip sanitize | PRIVATE = no external index protection. Collaborators (including external contributors) are exposed. Even 1 external member → this rule applies |
| 5 | Skip 4-grep self-check before `gh issue create` | Apply 4-grep to body variable before every `gh issue create/edit/comment` call. On match → sanitize and retry |

### 4-grep self-check (before every issue/PR body POST)

```bash
# 1. Local workspace paths (inaccessible to others)
grep -E '<workspace-name>/\.claude/|<repo-name>/\.claude/rules/|~/\.claude/skills/|~/\.agents/|\.ralph/|\.omc/' <body>

# 2. Internal RFC1918 IP / hosts
grep -E '10\.[0-9]+\.[0-9]+\.[0-9]+|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|EMC-|deps-(emc|dts|epe|daegun)' <body>

# 3. User home / personal path
grep -E '/Users/[a-z]+|/home/[a-z]+|C:/Users/' <body>

# 4. Internal tool names (externally unknowable)
grep -iE 'Semaphore Template [0-9]+|Authentik blueprint|fix_plan\.md|failed-attempts\.md' <body>
```

1 or more match → sanitize and retry. No autonomous bypass.

### Post-discovery

If found in already-posted body: immediately overwrite with `gh issue edit --body <sanitized>` or `gh pr edit --body <sanitized>`. GitHub edit history is permanent but minimize view exposure by immediate correction. Must record in failed-attempts.md HOT.

## GitHub Body Reference Notation (`#N`/SHA/URL/@mention) — HARD STOP

GitHub converts SHA/`#N`/@mention/URL in body/comment/review to autolinks. Backtick wrapping makes inline code → autolink does not fire. Per-type: **bare** (autolink intended) / **backtick·plain** (block) / **sub-bullet** (readability).

**Unified decision matrix**:

| Identifier | Type | Notation | Reason |
|------------|------|----------|--------|
| `#172` | Real issue/PR reference | **bare** `#172` | autolink → jump to that page |
| `#3` | Finding/item number (non-reference) | **backtick** `` `#3` `` or plain (`item 3`·`Important 3`) | bare creates unwanted issue/PR autolink → permanent timeline backref |
| Commit SHA (7+ chars) | commit reference | **bare** `de59590` | autolink → commit page |
| `@DrumRobot` | user mention | **bare** (backtick forbidden) | backtick invalidates mention |
| `https://github.com/...` | full URL | **bare** | autolink + preview |
| `(PR #371 Important #3, …)` | title suffix multi/supplemental ref | **separate `- ` sub-bullet** | inline embeds autolink titles into body text, reducing readability |

**Cross-repo reference** — bare `#N`·SHA only autolink **within the same repo**. Different repo requires `owner/repo` prefix:

| Target | GitHub | GitLab |
|--------|--------|--------|
| commit | `owner/repo@<sha>` | `ns/project@<sha>` |
| issue | `owner/repo#<id>` | `ns/project#<id>` |
| PR / MR | `owner/repo#<id>` | `ns/project!<id>` (`!` — not `#`) |

### Don't / Do

| # | Don't | Do |
|---|-------|----|
| 1 | Backtick SHA/URL/mention `` `de59590` `` | Write bare — autolink + preview/notification |
| 2 | Finding/item number bare (`Important #3`) | Backtick `` `#3` `` or plain |
| 3 | "#number/SHA is identifier so backtick" reasoning | Actual reference → bare. Non-reference number → backtick |
| 4 | Title suffix `(PR #371 Important #3, …)` inline | Separate sub-bullet |
| 5 | "Local doc·chat so notation doesn't matter" | bare↔backtick·sub-bullet is medium-agnostic |

**Self-check (before every ref output — Edit/Write/chat)**: ① scan `#[0-9]+` → real issue/PR=bare, finding=backtick ② SHA/`@user`/URL in backtick → correct to bare ③ title suffix multi/supplemental inline → split into sub-bullet

**Exception — backtick justified**: inside code block / inline code identifier (file path·function) / shell command containing SHA (`git show de59590`)


