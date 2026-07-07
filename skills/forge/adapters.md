# Adapters

Who implements the driver contract, per forge. This topic defines the **boundary** — it
does not implement the GitLab/Gitea adapters (that is Phase 2).

## Boundary map

```text
forge driver (interface contract — driver-interface + capability-matrix)
   ├── github  implementation = github-flow (existing gh calls wrapped as driver methods)
   ├── gitlab  adapter = glab mapping (Phase 2 — boundary only, not implemented)
   └── gitea   adapter = tea / API mapping (Phase 2 — boundary only, not implemented)
```

## github-flow refactor boundary

`github-flow` is the reference implementation. Making it a true adapter means moving its
direct host-CLI calls behind the driver methods across its topics. That refactor is
**out of scope for this contract** — it is broad (many topics) and carries regression risk,
so it is tracked as separate follow-up work (Phase 2). This skill only declares the boundary
so the refactor has a target contract to satisfy.

## Identity / auth precedent

The auth surface already has a good abstraction precedent: the owner→identity mapping is
workspace-scoped and externalized (owner rows kept out of the shared skill body). The
adapter only needs to map **scope** per forge:

| Forge | Auth scope shape |
|-------|------------------|
| GitHub | OAuth scopes (e.g., repo, read:org, workflow) |
| GitLab | token scopes (e.g., `api`, `read_repository`) |
| Gitea | personal access token |

`auth_status()` normalizes these into `{account, scopes[], ok}` so the pipeline checks
"authenticated with sufficient scope" without knowing the forge's native scope vocabulary.

## What Phase 2 adds

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 1 (this skill) | Driver interface + capability matrix + dispatch + adapter boundary | ✓ |
| 2 | Wrap `github-flow` host-CLI calls behind driver methods | pending |
| 2 | GitLab adapter (`glab` mapping) | pending |
| 2 | Gitea adapter (`tea` / API mapping) | pending |

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat this skill as a runtime shim that intercepts host calls | Treat it as a contract; the adapters (Phase 2) do the runtime wrapping |
| 2 | Refactor github-flow's topics as part of adopting this contract | Keep github-flow as-is now; the refactor is a scoped Phase 2 task with regression review |
| 3 | Duplicate auth scope logic per forge in the pipeline | Route through `auth_status()`; the adapter owns the scope-vocabulary mapping |
