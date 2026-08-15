# Actions (GitHub Actions Workflow)

Generates and manages GitHub Actions workflows matching the project type.

## Procedure

### 1. Project Analysis

Auto-detected items — `package.json`/`pyproject.toml` alone only confirm the *language*, not which package manager the templates below should target. Also check the lockfile/version-pin file to pick the right template variant:

- `package.json` → Node.js. Disambiguate manager: `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `package-lock.json` → npm. Check `.node-version` (or `engines.node` in `package.json`) for the Node version to pin in `node-version-file`/`node-version`.
- `pyproject.toml` / `setup.py` → Python. Disambiguate tool: `uv.lock` → uv (matches the "CI (Python + uv)" template below), otherwise plain pip/venv — the uv template does not apply, author a `pip install` step instead.
- `go.mod` → Go
- `Cargo.toml` → Rust
- `Chart.yaml` → Helm
- `Dockerfile` → Docker
- `pnpm-workspace.yaml` → Monorepo (confirms pnpm, not just Node.js)

### 2. Workflow Selection

Select required workflows via AskUserQuestion (multiSelect: true):

| Workflow | Description | Trigger | Canned template below |
|----------|-------------|---------|------------------------|
| ci (Node/pnpm) | Build + test + lint | push, PR | ✅ [CI (Node.js + pnpm)](#ci-nodejs--pnpm) |
| ci (Python/uv) | Build + test + lint | push, PR | ✅ [CI (Python + uv)](#ci-python--uv) |
| ci (Go/Rust) | Build + test + lint | push, PR | ❌ no template — author manually, following "Post-authoring Verification" below |
| release | Version tag → release creation | tag push | ✅ [Release (npm)](#release-npm) — npm-specific; other ecosystems need manual authoring |
| docker | Docker image build + push | push to main | ❌ no template — author manually, following "Post-authoring Verification" below |
| deploy | Deploy (ArgoCD sync, etc.) | release | ❌ no template — deploy targets are project-specific; author manually |
| helm | Helm chart packaging + GitHub Pages | push to main | ✅ [Helm Chart (GitHub Pages)](#helm-chart-github-pages) |
| dependabot | Automated dependency updates | schedule | ✅ [Dependabot](#dependabot) |

For any "❌" row selected, the workflow **still gets generated** — just hand-authored rather than templated. Follow "Post-authoring Verification" below regardless of template source.

### 3. Workflow Generation

Generate YAML files in the `.github/workflows/` directory.

## Workflow Templates

### CI (Node.js + pnpm)

```yaml
name: CI
on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main, develop]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: pnpm/action-setup@v6
      - uses: actions/setup-node@v7
        with:
          node-version-file: '.node-version'
          cache: 'pnpm'
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm typecheck
      - run: pnpm test
      - run: pnpm build
```

### CI (Python + uv)

```yaml
name: CI
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v9
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run pytest
```

### Release (npm)

```yaml
name: Release
on:
  push:
    tags: ['v*']

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v7
      - uses: pnpm/action-setup@v6
      - uses: actions/setup-node@v7
        with:
          node-version-file: '.node-version'
          cache: 'pnpm'
          registry-url: 'https://registry.npmjs.org'
      - run: pnpm install --frozen-lockfile
      - run: pnpm build
      - run: pnpm publish --no-git-checks
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
      - uses: softprops/action-gh-release@v3
```

### Helm Chart (GitHub Pages)

```yaml
name: Helm Chart
on:
  push:
    branches: [main]
    paths: ['charts/**']

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pages: write
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: azure/setup-helm@v5
      - run: |
          helm package charts/*
          helm repo index . --merge index.yaml
      - uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: .
```

### Dependabot

`.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: npm
    directory: /
    schedule:
      interval: weekly
    groups:
      dev-dependencies:
        dependency-type: 'development'
      production-dependencies:
        dependency-type: 'production'
    ignore:
      - dependency-name: '*'
        update-types: ['version-update:semver-major']

  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
```

**Why use `groups`**: Without `groups`, Dependabot creates one PR per package. Splitting into `dev-dependencies` and `production-dependencies` groups reduces PRs to 2. The `semver-major` ignore is optional — remove it if you want major version bumps auto-proposed.

## Post-authoring Verification

After writing a workflow YAML, verify **before committing**:

1. **Dependency install step**: Confirm each job installs the tools it uses (pytest, bats, lint, etc.). `actions/setup-python` installs Python only — pytest, ruff, etc. need a separate `pip install`.
2. **Local test run**: Run the commands the workflow will execute locally first to confirm they succeed.
3. **Action version check**: Check the actual latest major on the marketplace/repo (`gh api repos/<owner>/<action>/tags --jq '.[0].name'`) before generating — do not copy a version number from this doc's templates without re-verifying, since majors bump over time (e.g. `actions/checkout` moved v4→v7 between when these templates were first written and this check).

## Notes

- If an existing workflow file is present, **do not overwrite** — show diff and use AskUserQuestion.
- If secrets are needed, guide the user on how to set them (do not configure directly).
- Respect the "Honor GitHub Actions Workflows" rule in `~/.agent/rules/git.md`.
- Build artifacts (tgz, dist/) are generated by the workflow — do not commit them locally.
