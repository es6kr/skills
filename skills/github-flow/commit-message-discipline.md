# Commit Message Discipline — commit message authoring + message update on amend + PUBLIC repo English enforcement + git operation type continuity + verb selection (`.md` as source code)

## Conventional Commit Format

- Use Conventional Commit format: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`, `perf`
- **No tags outside the list above** (`infra:`, `build:`, `wip:`, and all other ad-hoc tags are forbidden)
- Choose language based on repository visibility: **PUBLIC = English mandatory, PRIVATE = Korean default** — the same visibility rule applies uniformly to commits, PRs, issues, and comments

## PUBLIC Repo Commit Message English Enforcement — Self-check (HARD STOP)

**Before every commit, confirm repository visibility + language via a first-hand source. English is mandatory for PUBLIC repos.** Blocks the pattern of dumping non-English thoughts directly into commit messages.

**Why**:
- PUBLIC repo commit history is permanent (even force-push amends remain in forks/clones)
- The mixed pattern of "Conventional Commit tags (`ci:`/`feat:`) in English but body parenthetical annotations in another language" is common
- Non-English thinking leaking directly into commit bodies occurs more often at the commit-message authoring stage than in code itself

| # | Don't | Do |
|---|-------|----|
| 1 | Commit message containing non-English words/sentences in a PUBLIC repo | Write the subject, body, and all parenthetical annotations in English |
| 2 | Mixed pattern: "Conventional Commit tags in English, body in another language" | All of tag + subject + body in English. Notes after hyphens must also be English |
| 3 | "The user decided/instructed in Korean, so use Korean in the commit message too" | User decision language does not equal commit message language. The commit medium always defers to the visibility rule |
| 4 | Skipping visibility confirmation before committing ("I already know it's a PUBLIC repo") | Confirm visibility from a first-hand source before every commit: `gh repo view <repo> --json isPrivate -q '.isPrivate'` |
| 5 | Assuming English enforcement is waived for PoC / draft / temporary commits | English is mandatory even for PoC commits in a PUBLIC repo. Even after a branch is deleted, git history persists in forks/clones |

**Self-check (before every commit message)**:

1. Is the target repo PUBLIC? — Latest visibility check result + `isPrivate=false`. If PRIVATE, this rule does not apply.
2. Does the written commit message subject + body contain non-ASCII characters in the Hangul syllable block (U+AC00 through U+D7A3)?
3. 1+ match — translate to English immediately
4. Visually scan the full message immediately before running `git commit -m`/`-F` or heredoc input
5. For cases corrected via amend + force push, verify post-hoc: `git log -1 --format=%B | grep -P '[\x{AC00}-\x{D7A3}]'` must return 0 matches

## Preserving Git Operation Type Continuity (HARD STOP)

**If the user specified a git operation type (amend / new commit / cherry-pick / rebase / squash / force push) in a prior ask/turn, maintaining the same type is the default for all subsequent related decisions.** Switching to a different operation type requires an explicit confirmation ask to the user.

### Don't / Do

| # | Don't | Do |
|---|-------|----|
| 1 | Processing a follow-up decision as a separate commit right after the user specified amend | Maintain the same amend type. If switching to a different type, ask the user explicitly |
| 2 | Defaulting to "a separate commit is safer (avoids force push)" | If the user specified amend, amend is the default. Proceed safely using `--force-with-lease` |
| 3 | Correcting a wrong commit made by an automation tool (e.g., a release-please 0.5.0 bump) with a separate downgrade commit | Directly amend the automation tool's commit. Maintain a single clean commit at the PR head |
| 4 | Interpreting the user-specified operation as "one-time only for the last turn" | User specifying a type means it applies for the entire current work flow. Automatically maintain the same type for subsequent decisions |
| 5 | Avoiding force push after amend under the premise "force push is risky" and adding a separate commit instead | If the user specified amend + force push, `--force-with-lease` is the correct approach |

### Self-check (before every commit)

1. Did the user specify a git operation type in a prior ask/turn? (amend, new commit, rebase, cherry-pick, squash, force push, etc.)
2. If so, is the current decision also the same type?
3. Considering a different type? — Stop immediately and ask the user for explicit confirmation
4. Is this a situation where a wrong commit made by an automation tool needs to be corrected? — Prioritize history cleanliness and choose amend

### Exceptions

- User did not specify a type → default = new commit (safe)
- The amend target is another person's published commit or a protected branch like main/master → force push itself is forbidden

## Mandatory Message Update on --amend

**When adding/changing files via `git commit --amend`, the commit message must also be updated.**

- Do not use `--no-edit` (it leaves the message out of sync with the actual changes)
- **Exception**: minor changes such as typo fixes or formatting where a message update is unnecessary

## Commit Tag Selection Criteria

- `feat`: new functionality end users interact with directly (UI, API endpoints, CLI commands, etc.)
- `test`: adding or modifying test code (test files, fixture data, test configuration)
- `ci`: CI/CD workflows, test infrastructure configuration (GitHub Actions, Playwright setup, CI configuration)
- **When test infrastructure and test code are mixed**: use `ci`
- `feat` must not be used for: adding e2e tests, adding test fixtures, adding CI pipelines

## Verb Selection — skill/rule `.md` files are source code (HARD STOP)

**Commit message verbs for changes to `skills/**/*.md`, `rules/**/*.md`, and `.claude/rules/**/*.md` files must describe a behavior change. Documentation verbs (`document`, `describe`, `note`) are forbidden.**

Rationale: These files are **directives** consumed by the AI agent at runtime. Adding or editing Markdown text means adding or modifying agent behavior — not documenting pre-existing behavior.

### Allowed vs Forbidden Verbs

| Type | Verbs |
|------|-------|
| **Behavior-change verbs** (use for skill/rule `.md`) | `add`, `introduce`, `require`, `mandate`, `enforce`, `prohibit`, `forbid`, `allow`, `replace`, `restructure`, `remove`, `tighten`, `relax`, `extend` |
| **Documentation verbs** (forbidden for skill/rule `.md`) | `document`, `describe`, `note`, `clarify wording`, `fix typo` (limited to behavior-neutral changes such as typo fixes and copy cleanup) |

### Don't / Do

| # | Don't | Do |
|---|-------|----|
| 1 | `feat(wip): document Copilot rate-limit cache write` | `feat(wip): require Copilot rate-limit reset timestamp shared-cache write` |
| 2 | `docs(skill-X): describe new behavior` (when in fact new behavior is being added) | `feat(skill-X): add/introduce/enforce <new behavior>` — the `docs:` prefix is reserved for behavior-neutral changes such as typo fixes, formatting, and link updates |
| 3 | Defaulting to "`docs:` for any `.md` text addition" | skill/rule `.md` files are AI source. Adding a new rule/HARD STOP/Don't-Do row = `feat:`. Removing a rule = `feat:` (behavior change). Meaning-identical refactoring = `refactor:` |
| 4 | Using a behavior verb in the subject but framing the body as "documents that X must Y" | Frame the body as "this commit changes how the agent behaves: X must now Y" — explicitly describe the behavior change |

### Self-check (before drafting every commit message)

1. Is at least one changed file a `skills/**/*.md`, `rules/**/*.md`, or `.claude/rules/**/*.md`?
2. If yes, does the commit message verb match an entry in the "Forbidden verbs" table?
3. If it matches — re-check whether the diff actually adds new behavior / HARD STOP / Don't-Do rows / self-check steps
4. If it is a behavior change — select a verb from the "Allowed verbs" table. If the type prefix was `docs:`, replace it with `feat:`

### Exceptions

- The file is a skill/rule `.md` but the change is purely a typo fix, formatting, or link correction with no behavior change → `docs:` + documentation verb is acceptable
- Only external references or example text in a skill/rule `.md` are updated (rules/procedures unchanged) → `docs:` is acceptable
