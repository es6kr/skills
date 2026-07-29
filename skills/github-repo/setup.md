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

Enables Copilot suggestions in public repositories.

**Procedure**:
1. Check visibility with `gh repo view --json isPrivate`.
2. If public, create `.github/copilot-instructions.md`.

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
2. Choose protection options:
   - Required review count
   - Required status checks
   - Prohibit force push
3. Call `gh api repos/{owner}/{repo}/branches/{branch}/protection`.

**Note**: If protection rules already exist, AskUserQuestion is required before overwriting.

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
