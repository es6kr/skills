# Setup (Integration Configuration)

Configures external service integrations and standard files for a GitHub repository.

## Configuration Items

### 1. CodeRabbit (AI Code Review)

Creates `.coderabbit.yaml` at the repository root.

**Procedure**:
1. Check if `.coderabbit.yaml` already exists.
2. If absent, create the standard configuration.

**Standard configuration**:
```yaml
language: ko
reviews:
  auto_review:
    enabled: true
    drafts: false
  path_instructions:
    - path: "**/*.test.*"
      instructions: "Focus on test coverage and edge cases"
    - path: "**/*.md"
      instructions: "Check accuracy and completeness of documentation"
chat:
  auto_reply: true
```

**User confirmation**: Use AskUserQuestion to ask whether additional `path_instructions` are needed.

### 2. GitHub Copilot (Public repositories)

Adds Copilot instructions for repositories where Copilot review/suggestions are actually enabled. Public visibility alone does not turn Copilot on — it also requires an org/billing prerequisite (a Copilot seat or an org-level Copilot policy allowing the repo). Creating `.github/copilot-instructions.md` on a repo without that prerequisite is a no-op file with nothing consuming it.

**Procedure**:
1. Check visibility with `gh repo view --json isPrivate`.
2. Check the org's Copilot seat/policy status is in place (e.g. `gh api orgs/{org}/copilot/billing` or the org's Copilot settings page) — do not assume public visibility implies an active seat.
3. If public AND Copilot is actually enabled for the repo, create `.github/copilot-instructions.md`.

**Standard configuration**:
```markdown
# Copilot Instructions

## Project Context
[Project description — confirm with user]

## Code Style
[Extracted from CONTRIBUTING.md or .editorconfig]

## Conventions
[Commit rules, naming conventions, project-specific rules]
```

**User confirmation**: Confirm project description and conventions via AskUserQuestion.

### 3. Issue Templates

Creates issue templates under `.github/ISSUE_TEMPLATE/`.

**Standard template set**:
- `bug_report.yml` — Bug report
- `feature_request.yml` — Feature request

**Procedure**:
1. Check if `.github/ISSUE_TEMPLATE/` exists.
2. If absent, select needed templates via AskUserQuestion (multiSelect).
3. Generate selected templates.

### 4. PR Template

Creates `.github/pull_request_template.md`.

**Standard template**:
```markdown
## Summary
<!-- Describe what changed -->

## Changes
-

## Test plan
- [ ]

## Related issues
<!-- Relates to # -->
```

### 5. CODEOWNERS

Creates `.github/CODEOWNERS`.

**Procedure**:
1. Confirm owner mappings via AskUserQuestion.
2. Set per-directory owners.

**Example**:
```
* @owner
/docs/ @docs-team
/src/api/ @backend-team
```

### 6. Branch Protection

Configure branch protection rules via `gh api`.

**Procedure**:
1. Confirm which branches to protect via AskUserQuestion (default: main).
2. **Read the existing protection first**: `gh api repos/{owner}/{repo}/branches/{branch}/protection` (404 = none configured yet). The branch-protection endpoint is a full-replace `PUT` — omitting a field that was previously set (e.g. an existing required status check, dismissal restriction, or reviewer count) deletes it, not merely "leaves it unspecified".
3. Choose protection options, merging into the existing payload from step 2 rather than starting from a blank template:
   - Required review count
   - Required status checks
   - Prohibit force push
4. Call `gh api repos/{owner}/{repo}/branches/{branch}/protection` with the **full merged payload** (existing settings + the new/changed ones).

**Note**: If protection rules already exist, AskUserQuestion is required before overwriting — show the user which existing fields step 2 found so they can confirm nothing is being silently dropped.

## Execution

### Full setup

```
/github-repo setup
```

Select items via AskUserQuestion (multiSelect):
- CodeRabbit
- Copilot (Public only)
- Issue Templates
- PR Template
- CODEOWNERS
- Branch Protection

### Individual setup

```
/github-repo setup coderabbit
/github-repo setup copilot
/github-repo setup templates
/github-repo setup codeowners
/github-repo setup protection
```

## Notes

- If a file already exists, **do not overwrite** — show diff first, then use AskUserQuestion.
- `copilot-instructions.md` is optional for private repositories (confirm via AskUserQuestion).
- Branch protection requires admin privileges — if unavailable, guide the user instead of applying directly.
