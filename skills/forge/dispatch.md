# Dispatch

How a pipeline resolves *which* forge driver to use. Reuses the established
`--<verb>=<target>` dispatch idiom (the same shape as `--rag=<skill>:<topic>`), so no new
mechanism is introduced.

## Flag

```
--forge=<github|gitlab|gitea>     # explicit override
```

An explicit `--forge=` always wins. When omitted, the driver is auto-detected.

## Auto-detection (flag omitted)

1. Parse the host from `git remote get-url origin`:
   - `github.com` → github
   - `gitlab.*` → gitlab
   - otherwise (self-hosted) → infer from repo signals: a `.gitlab-ci.yml` file or a
     `glab` binary suggests gitlab; a `tea` binary or Gitea API reachability suggests gitea.
2. If inference fails → default to **github** (preserves current behavior) and log a warning.
3. This auto-detection replaces the single hardcoded `github.com` host check in the
   consumer pipeline's Step 0 forge detection — that seam is the one place the forge was
   previously hardcoded.

## Backward compatibility

Because an unresolved forge falls back to **github**, existing GitHub-only users are
unaffected: no flag, a `github.com` remote, and the pipeline behaves exactly as before. The
abstraction is opt-in for non-GitHub hosts and transparent for GitHub.

## Caller contract

The pipeline that consumes a forge driver should:

1. Read `--forge=` if the user supplied it.
2. Otherwise run auto-detection once, at pipeline entry, and cache the resolved driver.
3. Pass the resolved driver to every subsequent operation so a single run never mixes
   forges.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Re-detect the forge on every operation | Resolve once at entry; cache and reuse for the whole run |
| 2 | Hard-fail when the host is unrecognized | Fall back to `github` + warn (backward compatibility) |
| 3 | Keep the `github.com` string check inline in the consumer pipeline | Route host detection through this dispatch so all forges share one code path |
| 4 | Let an explicit `--forge=` be overridden by auto-detection | Explicit override always wins over inference |
