# PR Creation

Create PRs with structured body, test plan, and optional visual attachments.

## When to Use

- After code-workflow step 4 (implement) to create a PR
- When the user says "create PR", "PR with screenshots"
- After capture step (if visual evidence is needed)

## Options

- `--draft`: Create as Draft PR (`gh pr create --draft`)
- `--skip-review`: Skip CodeRabbit review (`--label coderabbit:ignore`)
- `--no-capture`: Skip visual attachment step
- Options can be combined: `/github-flow pr --draft --skip-review`

## Procedure

### Step 1: Pre-flight Checks

```bash
# Detect base branch
BASE=$(git merge-base HEAD master 2>/dev/null && echo master || echo main)

# Check gh CLI
gh --version 2>/dev/null || echo "gh not found"

# Check for existing open PR on this branch
gh pr list --head $(git branch --show-current) --state open
```

- If **gh CLI missing** → proceed with body template only (no creation)
- If **PR already exists** → report to user and stop

### Step 2: Gather Changes

```bash
git log --oneline origin/$BASE..HEAD   # commits to include
git diff --stat origin/$BASE           # changed files summary
```

### Step 3: Search Related Issues (gh CLI only)

Extract keywords from branch name and changed files, search for related issues:

```bash
gh issue list --limit 100 --state open --search "[keywords]"
```

Present 1-3 candidates via **AskUserQuestion** for confirmation.
If no issues found, skip this section.

### Step 4: Construct PR Body

If `.github/pull_request_template.md` exists, use that template. Otherwise use the default below.

```markdown
## Summary
<1-3 bullet points>

## Changes
| File | Change |
|------|--------|
| ... | ... |

## Related Issues
<!-- Relates to #number — Do NOT use "Closes #" or "Fixes #" to prevent auto-close -->

## Visual Changes (optional)
| Before | After |
|--------|-------|
| ![before](url) | ![after](url) |

## Test plan
- [ ] Local build passes
- [ ] No type errors
- [ ] ...

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

**Checklist inclusion criteria** — only include items relevant to the change:

| Item | Include when |
|------|-------------|
| Local build passes | Always |
| No type errors | Always |
| Route/sidebar navigation works | UI page add/change |
| Core feature works | Functional changes |
| DB/API integration verified | DB/API changes |

For chore/docs/config changes, only build + type check items.

### Step 5: Sanitize Internal Paths

Before posting, strip all internal paths per SKILL.md Core Rules:
- `.ralph/docs/` references → remove or inline the content
- Session IDs → remove
- `.omc/` references → remove

### Step 6: Review and Create PR

Show the drafted title and body to the user via **AskUserQuestion** for confirmation.

**With gh CLI:**

```bash
gh pr create \
  --title "..." \
  --body "$(cat <<'EOF'
...
EOF
)" \
  --base $BASE \
  --head $(git branch --show-current) \
  --label [label] \
  --add-assignee @me
```

- `--draft` option → add `--draft` flag
- `--skip-review` option → add `--label coderabbit:ignore` (in addition to classification label)
- **At least 1 classification label required**: enhancement, bug, documentation, test, chore, etc.

Report the PR URL after creation.

**Without gh CLI:** output the body in a code block for manual use.

### Step 7: Attach Visual Evidence (optional)

If capture was performed (code-workflow Step 5) and `--no-capture` not set:

| Method | When |
|--------|------|
| GitHub image upload (preferred) | PR-only visual evidence |
| `.github/assets/` directory | Permanent documentation |

**Do not commit screenshots** unless they serve as permanent docs.

### Image Format Priority

| Format | Use Case |
|--------|----------|
| WebP | Static screenshots (smallest, GitHub supported) |
| PNG | When WebP unavailable or transparency needed |
| GIF | Short animations, hover effects |
| MP4/WebM | Complex interactions |

### Capture Naming

```text
.github/assets/<issue-number>-<description>-before.webp
.github/assets/<issue-number>-<description>-after.webp
```

## Rules

- **`Closes #` / `Fixes #` keyword forbidden** — use `Relates to #` to prevent auto-close of linked issues
- **At least 1 classification label** required on every PR
- **Sanitize internal paths** before posting (Step 5)
