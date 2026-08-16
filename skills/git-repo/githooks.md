# githooks — why a repo's `.githooks/` silently does nothing

Diagnosing "my hook isn't running", and choosing an install method that does not
silently disable the machine-wide hooks.

## The three independent reasons a `.githooks/` hook is ignored

Check all three — they compound, and fixing only one leaves the hook dead.

| # | Cause | Check | Symptom |
|---|-------|-------|---------|
| 1 | `core.hooksPath` points elsewhere | `git config --get core.hooksPath` | git reads ONLY that directory — both `.githooks/` and `.git/hooks/` are bypassed |
| 2 | `.githooks/` is not a git convention | — | git never auto-discovers `.githooks/`. It is a naming convention that requires an explicit `core.hooksPath=.githooks` per repo (git 2.9+) |
| 3 | Hook file lacks the execute bit | `ls -l .githooks/<hook>` | git skips non-executable hooks **silently** — no warning, no error |

Diagnostic sequence:

```bash
R=<repo>
git -C "$R" config --local  --get core.hooksPath   # repo-level override
git config --global --get core.hooksPath           # machine-wide default
git config --system --get core.hooksPath
git -C "$R" rev-parse --git-path hooks             # the directory git will actually read
ls -l "$R/.githooks/"                              # execute bit present?
```

`rev-parse --git-path hooks` is the authoritative answer to "which directory does
git read for this repo" — it already resolves the local/global/system precedence.

## When a machine-wide `core.hooksPath` is in play

A global `core.hooksPath` disables every repo's `.git/hooks/` too, which would break
repos that already had local hooks. The usual mitigation is a **passthrough chain**:
each hook in the global directory re-executes the repo's own hook of the same name.

```bash
# A passthrough hook, copied under each hook name in the global hooks directory
HOOK_NAME="$(basename "$0")"
LOCAL_HOOK="$(git rev-parse --absolute-git-dir 2>/dev/null)/hooks/$HOOK_NAME"
if [ -x "$LOCAL_HOOK" ] && [ "$LOCAL_HOOK" != "$0" ]; then
  exec "$LOCAL_HOOK" "$@"
fi
exit 0
```

Two properties matter when reasoning about such a setup:

- The chain forwards to **`.git/hooks/<name>`**, never to `.githooks/<name>`. A repo
  that keeps hooks in `.githooks/` gets nothing from the chain.
- Hooks that carry real validation logic run their own checks **first** and only then
  fall through to the same chain block. So a repo-local hook of that name runs *in
  addition to* the global validation, not instead of it.

Classify the global hooks before deciding anything — passthrough stubs and real
validators behave differently:

```bash
H="$(git config --global --get core.hooksPath)"
for f in "$H"/*; do
  cmp -s "$f" "$H/_chain" && kind=passthrough || kind=REAL
  printf '%-24s %6sB  %s\n' "$(basename "$f")" "$(wc -c <"$f" | tr -d ' ')" "$kind"
done
```

Identical byte size to the passthrough template is the quick tell; `cmp` confirms it.

## Install method trade-off (HARD STOP — read before setting `core.hooksPath` locally)

`core.hooksPath` holds a **single value**. Setting it locally *replaces* the global
one — it does not layer. Any validation living in the global hooks directory stops
running for that repo, silently.

| Method | Global hooks | Version-controlled | Failure mode |
|--------|--------------|--------------------|--------------|
| `git config core.hooksPath .githooks` | **Lost** (local value replaces global) | Yes | Machine-wide validators (commit-message format, push gates) silently stop for this repo |
| Copy `.githooks/*` → `.git/hooks/` | Kept (passthrough chain re-executes them) | No — `.git/` is not tracked | Drift: editing `.githooks/` does not propagate; a fresh clone has no hooks until someone re-runs the install step |
| Local `core.hooksPath=.githooks` + shim | Kept | Yes | Needs one shim per global hook name; shim path is machine-specific |

The shim is the third option that most write-ups omit — keep the tracked directory
*and* the global validation:

```bash
# .githooks/commit-msg
#!/bin/bash
exec "$(git config --global --get core.hooksPath)/commit-msg" "$@"
```

| # | Don't | Do |
|---|-------|-----|
| 1 | Set `core.hooksPath` locally without first listing what the global hooks directory contains | Classify global hooks (passthrough vs real) first — only then decide whether losing them is acceptable |
| 2 | Assume `.githooks/` works because the repo next door has it | That repo has a **local** `core.hooksPath`. Confirm with `git -C <repo> rev-parse --git-path hooks` |
| 3 | Disable a machine-wide validator by repointing `core.hooksPath`, when the validator has a per-repo opt-out | Check the validator for an opt-out switch (`git config --get hooks.<name>` style) and use that instead |
| 4 | Copy-install and consider it done | Copy-install has no propagation. Record the install step somewhere the next clone will see it, and re-run it after editing `.githooks/` |
| 5 | Debug a non-firing hook by reading its body | Check the execute bit first — a non-executable hook fails silently, and the passthrough chain's `[ -x ... ]` test skips it too |

## Self-check (before changing any hook wiring)

1. Which directory does git actually read? — `git rev-parse --git-path hooks`
2. If a global `core.hooksPath` exists, which of its hooks are real validators vs passthrough stubs?
3. Does the change drop any real validator for this repo? If yes, is there a per-repo opt-out that expresses the intent more narrowly?
4. Are the hook files executable?
5. If copy-installing, where is the re-run step recorded so the next clone (and the next edit of `.githooks/`) does not silently regress?

## Worked example (2026-08-17)

A repo's `.githooks/pre-commit` (a guard blocking an untracked tracker file from
being staged) had never fired. All three causes were present at once:

- global `core.hooksPath` was set, so `.githooks/` was never read
- the global `pre-commit` was a passthrough stub forwarding to `.git/hooks/pre-commit`,
  which did not exist in that repo
- the hook file was `-rw-r--r--` — no execute bit

A sibling repo in the same workspace *did* work, because it had a **local**
`core.hooksPath=.githooks` and executable hooks. That same local override, though,
meant its commits bypassed the machine-wide commit-message validator entirely: its
`.githooks/` contained only `pre-commit` and `pre-push`, no `commit-msg`. Neither
repo's owner had noticed either effect, which is the whole hazard — every failure
mode in this topic is silent.
