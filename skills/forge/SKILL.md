---
name: forge
depends-on: [github-flow]
metadata:
  author: es6kr
  version: "0.0.0"
description: |
  Forge-agnostic git-host driver contract. Lets code-workflow / github-flow / harness
  pipelines run independent of the underlying git forge (GitHub, GitLab, Gitea) through a
  normalized driver interface + a `--forge=<github|gitlab|gitea>` dispatch idiom with
  git-remote auto-detection (github fallback). Use when: designing or reasoning about
  forge-portable PR/MR/issue/merge operations, adding a new forge adapter, deciding how a
  pipeline should degrade when a forge lacks a capability (PR↔PR dependency, sub-issues,
  Copilot review), or normalizing repo visibility (PUBLIC/INTERNAL/PRIVATE) and reference
  formats (`#N` vs MR `!N`) across hosts. Triggers: "forge", "forge-agnostic", "--forge",
  "forge driver", "gitlab", "gitea", "glab", "tea", "MR", "capability flag", "adapter".
---

# Forge

Forge-agnostic driver contract for git-host operations. Pipelines (code-workflow,
github-flow, harness, consolidate) call **normalized driver methods** instead of a
specific host's CLI, so the same pipeline works on GitHub, GitLab, or Gitea.

`github-flow` is the **GitHub implementation** of this contract. GitLab (`glab`, MR `!N`)
and Gitea (`tea`/API) are **adapter boundaries** — declared here, implemented in Phase 2.

> Scope note: this skill defines the **interface, capability matrix, and dispatch**. It is
> a design contract, not a runtime shim. Wrapping `github-flow`'s existing `gh` calls behind
> the driver, and writing the GitLab/Gitea adapters, are separate follow-up work (Phase 2).

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| driver-interface | Normalized driver methods (pr/issue/merge/auth/visibility/ref/dependency) + normalized return types | [driver-interface.md](./driver-interface.md) |
| capability-matrix | Per-forge capability flags + how the pipeline degrades when a capability is absent | [capability-matrix.md](./capability-matrix.md) |
| dispatch | `--forge=<driver>` override + git-remote auto-detection + github fallback | [dispatch.md](./dispatch.md) |
| adapters | Adapter boundary: github-flow = GitHub impl; gitlab/gitea = Phase 2 boundary | [adapters.md](./adapters.md) |

## Topic Dependencies

```text
forge (driver contract)
  ├─→ dispatch (entry — resolve which driver to use)
  │     └─→ driver-interface (the resolved driver's method contract)
  │           └─→ capability-matrix (query before calling; degrade if unsupported)
  └─→ adapters (who implements the contract per forge)
        └─→ github-flow (GitHub implementation — depends-on)
```

- **dispatch** is the entry point: resolve `--forge=` or auto-detect from the git remote.
- **driver-interface** is the method contract every adapter must satisfy.
- **capability-matrix** is consulted before an operation to pick native vs emulated path.
- **adapters** maps each forge to its implementation; `github-flow` is the reference impl.

## Quick Reference

### Dispatch

```
--forge=<github|gitlab|gitea>     # explicit override
# omitted → auto-detect from `git remote get-url origin` host; unresolved → github fallback
```

See [dispatch.md](./dispatch.md).

### Driver methods (normalized)

`pr_create` · `pr_view` · `pr_merge` · `pr_checks` · `issue_create` · `issue_edit` ·
`repo_visibility` (→ enum `PUBLIC|INTERNAL|PRIVATE`) · `auth_status` · `ref_format` ·
`dep_block` · `review_bots`. Each returns a **normalized** shape so callers stay
forge-agnostic. See [driver-interface.md](./driver-interface.md).

### Capability flags

`pr_pr_dependency` · `sub_issue` · `issue_dependency` · `visibility_domain` ·
`reviewer_copilot` · `reviewer_coderabbit`. Query before an operation; if unsupported,
follow the degrade path (emulation or skip). See [capability-matrix.md](./capability-matrix.md).

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--forge=<driver>` | auto-detect → `github` | Select the forge driver. Explicit override wins; otherwise resolved from the git remote host, falling back to `github` for backward compatibility. |

## See Also

- `github-flow` (depends-on) — the GitHub implementation of this driver contract
- `code-workflow` — primary consumer; its Step 0 forge detection is the seam this abstracts
- `harness` — pipeline harness that runs forge-agnostic operations through this contract
- `skill-kit/portability` — abstract dispatch contract (`--forge=` idiom) rationale
