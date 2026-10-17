# Feature Base Guard — OpenClaw Adapter

This user-owned source plugin runs its package-local Git preflight at
`resources/verify_feature_base.py`, a byte-identical copy of the canonical
`skills/git-repo/scripts/verify_feature_base.py`. OpenClaw captures the package
body, not surrounding monorepo siblings; resolution stays inside the captured
package and does not depend on host `rootDir` or a developer filesystem path.
When updating the canonical helper, refresh the packaged copy and run the
byte-parity regression. Default npm package inclusion includes this resource. It has no network requests,
credentials or npm runtime dependencies. Load the local development package
through OpenClaw's supported plugin management/config surface; do not modify
Gateway configuration through shell scripts.

## Supported routes and limits

The supported tool is `feature_base_action` with a configured `contractId` and
one action: `start`, `commit`, or `deliver`. The host's `before_tool_call` hook
runs the common helper and returns `{block: true, blockReason}` on any failure.
The tool also rechecks at execution; `commit` invokes only argv-based
`git -C <configured-repo> commit -m <message>` on **already staged** content,
then performs clean final delivery verification. It never stages, branches,
fetches, pushes, merges, resets, or removes worktrees. Configure the final count
for the particular logical commit; the pre-commit count is final count minus
one. Post-commit rejection reports failure and preserves the commit.

This is **not** a universal shell/code-mode Git mutation detector. Arbitrary
`exec`, nested Code Mode, native shell aliases, scripts and other Git tools are
outside its interception coverage. Do not claim they are protected or infer
Git commands with regex. Acquisition/relocation use the common procedural
start/deliver gate; migrate mutations to a supported structured route or add a
separately documented adapter before claiming runtime enforcement there.

No return/Stop hook prevents natural turn completion. Standalone policy tests
and source hash equality do not prove native veto activation. The helper check
and commit are not an atomic repository lock; preserve concurrent-owner work.

## Configuration contract

The manifest validates a nonempty `contracts` mapping. Each contract pins an
absolute worktree root, full base SHA, final expected count and literal allowed
paths. Caller input cannot override any of these. Instance values belong in
local Gateway settings, never this public source.

```json
{
  "contracts": {
    "feature-task": {
      "repo": "<absolute-worktree-root>",
      "base": "<full-base-sha>",
      "expectedCommits": 1,
      "allowedPaths": ["src/owned-file.py", "tests/owned-test.py"]
    }
  }
}
```

## Parent-controlled runtime handoff

1. Inspect current configuration and loaded plugin inventory through supported
   OpenClaw tools. Preserve existing load paths, allowlist, entries and settings.
2. Add this package's absolute directory to `plugins.load.paths`, append
   `feature-base-guard` to `plugins.allow` if an allowlist is present, and set
   `plugins.entries.feature-base-guard.enabled = true` plus its `config`.
3. Apply/reload through the supported OpenClaw plugin/config lifecycle. The
   documented hybrid reload normally reflects load-path changes. If a restart
   is necessary, use the supported lifecycle capability under task authority.
4. Inspect the native runtime: plugin id, hook registration and tool ownership.
   Invoke actual `feature_base_action` delivery once on a valid configured
   one-commit feature (allow) and once on a configured unrelated multi-commit
   feature (terminal block). Both are read-only and have no API costs.
5. Record native call ids/results and runtime receipts separately from source
   implementation and standalone regression. A missing native tool/hook or
   rejected config remains an explicit runtime blocker, not success.

Primary host contracts: installed OpenClaw `docs/plugins/hooks/tool-policy.md`
(terminal veto, host discriminators, load paths),
`docs/plugins/building-plugins.md` (entry/manifest/tool registration), and
`docs/plugins/manifest.md` (pre-runtime config validation). Local source entry
is `index.ts`; `policy.mjs` is testable without booting a Gateway. This package
is private/local-development-only; publication requires a built SDK-compatible
entry and separate authority.

Process failures report fixed categories (`missing-helper`, `helper-unavailable`,
`missing-interpreter`, `timeout`, `output-limit`, `process-failed`,
`malformed-receipt`, `rejected-contract`, `invalid-repo`). Raw stderr and arbitrary
helper error text are never relayed; bounded known semantic rejection messages
(such as commit-count mismatch) remain visible.

Source changes do not replace an already captured runtime package. The parent
must recapture/reload through the supported lifecycle and obtain both actual
native allow and terminal-veto receipts before marking runtime repair complete.
Keep the original one-commit agent-task contract unchanged; a source repair
branch with multiple logical commits requires a separate truthful task contract.

## Checks

```bash
python3 -m unittest discover -s tests -p 'test_verify_feature_base.py'
python3 -m unittest discover -s tests -p 'test_staging_feature_base.py'
node --test tests/test_feature_base_adapter.mjs
```
