---
name: github-repo
metadata:
  author: es6kr
  version: "0.1.0"
depends-on:
  - github-flow
description: |
  GitHub repository configuration and verification. Topics — actions (GitHub Actions workflow generation + Dependabot grouping by dependency type), setup (integrations: CodeRabbit, Copilot, issue/PR templates, CODEOWNERS, branch protection), verify (repo prerequisites checklist for github-flow: remote, default branch, PR template, branch protection, GitHub Actions, CONTRIBUTING, LICENSE). Use when: "github actions", "workflow generation", "CI workflow", "dependabot", "dependabot groups", "coderabbit", "copilot setup", "GitHub Actions", "repo setup", "CODEOWNERS", "PR template", "issue template", "branch protection", "repo verify".
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash(gh:*)
  - Bash(git:*)
  - Bash(ls:*)
  - Bash(mkdir:*)
---

# GitHub Repo

GitHub repository configuration, integrations, and prerequisite verification.

Extracted from the `github` skill (formerly `skills/github/`) and tracked under `.agents/skills/github-repo/` for git management.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| actions | GitHub Actions workflow generation/management + Dependabot configuration (groups by dependency type) | [actions.md](./actions.md) |
| setup | Integrations setup: CodeRabbit, Copilot, issue templates, PR template, CODEOWNERS, branch protection | [setup.md](./setup.md) |
| verify | Repo prerequisites checklist for `github-flow` (remote, branch, templates, CI, protection) | [verify.md](./verify.md) |

## Quick Reference

### Repository initial setup

```
/github-repo setup                    # interactive setup item selection
/github-repo setup coderabbit         # CodeRabbit only
/github-repo setup copilot            # Copilot setup
/github-repo setup templates          # issue/PR templates
/github-repo setup protection         # branch protection
```

### Configuration verification

```
/github-repo verify                   # full prerequisites check
```

### Actions workflows + Dependabot

```
/github-repo actions                  # generate workflow for project type
/github-repo actions dependabot       # create/update dependabot.yml
```

## Migration Note

This skill was extracted from the `github` skill (`skills/github/`, gitignored).
The old `/github actions`, `/github setup`, `/github verify` triggers are
replaced by `/github-repo actions`, `/github-repo setup`, `/github-repo verify`.
