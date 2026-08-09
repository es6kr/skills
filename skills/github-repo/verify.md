# Verify (Repository Configuration Check)

Verifies that a GitHub repository has the prerequisites needed to run `github-flow`.

## Verification Checklist

### Required Items

| # | Item | Verification | Pass Criteria |
|---|------|--------------|---------------|
| 1 | Remote config | `git remote -v` | origin points to a GitHub URL |
| 2 | Default branch | `gh repo view --json defaultBranchRef` | main or develop exists |
| 3 | Visibility | `gh repo view --json isPrivate` | Record result (no pass/fail) |
| 4 | PR template | `.github/pull_request_template.md` exists | File present |
| 5 | Issue templates | `.github/ISSUE_TEMPLATE/` exists | Directory + at least 1 file |
| 6 | Branch protection | `gh api repos/{o}/{r}/branches/{b}/protection` | main/develop protection configured |

### Recommended Items

| # | Item | Verification | Pass Criteria |
|---|------|--------------|---------------|
| 7 | CODEOWNERS | `.github/CODEOWNERS` exists | File present + valid format |
| 8 | CodeRabbit | `.coderabbit.yaml` exists | File present |
| 9 | Copilot | `.github/copilot-instructions.md` exists | Repos with Copilot seat/policy enabled (any visibility) |
| 10 | GitHub Actions | `.github/workflows/` exists | At least 1 workflow file |
| 11 | CONTRIBUTING | `CONTRIBUTING.md` exists | File present |
| 12 | LICENSE | `LICENSE` exists | File present |

### Ralph-specific Items

Prerequisites for running Ralph's `github-flow.md`:

| # | Item | Verification | Pass Criteria |
|---|------|--------------|---------------|
| 13 | Open PR | `gh pr list --state open --assignee @me` | At least 1 assigned PR |
| 14 | Branch match | Current branch = PR headRefName | Match |
| 15 | Labels | Issue has labels | Ralph task classification labels present |

## Execution Procedure

1. Collect repo info with `gh repo view`.
2. Verify required items in sequence.
3. Verify recommended items in sequence.
4. If a Ralph project, verify Ralph-specific items.
5. Output results.

## Output Format

```
## Repository Configuration Verification

**Repository**: owner/repo (Public/Private)
**Default branch**: main

### Required
- ✅ Remote config: origin → github.com/owner/repo
- ✅ Default branch: main
- ❌ PR template: missing
- ❌ Issue templates: missing
- ⚠️ Branch protection: main not protected

### Recommended
- ❌ CODEOWNERS: missing
- ❌ CodeRabbit: missing
- ✅ GitHub Actions: 2 workflows
- ✅ CONTRIBUTING.md: present
- ✅ LICENSE: MIT

### Summary
- Required: 3/6 passed
- Recommended: 3/6 passed
- Fix missing items: run `/github-repo setup`
```

## Auto-fix Suggestions

After outputting results, suggest fixes for failed items via **AskUserQuestion `questions` array** — required and recommended in separate questions:

```
AskUserQuestion {
  questions: [
    {
      question: "Select required items to configure automatically.",
      header: "Required",
      multiSelect: true,
      options: [
        // Failed required items only (e.g. PR template, issue templates, branch protection)
      ]
    },
    {
      question: "Select recommended items to configure automatically.",
      header: "Recommended",
      multiSelect: true,
      options: [
        // Failed recommended items only (e.g. CODEOWNERS, CodeRabbit, CONTRIBUTING)
      ]
    }
  ]
}
```

### Rules

- Omit the question for a category if there are no failures in it (exclude from `questions` array).
- If `isPrivate: false` (open-source), include a note to generate content in English.
- Selected items are handed off to the corresponding procedure in `/github-repo setup`.
