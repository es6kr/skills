# Hunk Split

Stage a subset of a file's unstaged hunks non-interactively, when `git add -p` cannot be scripted (headless tool sessions, automation contexts where interactive TTY input isn't available).

## When to Use

- A single file has 2+ unrelated diff hunks (e.g., a pre-existing unrelated change already sitting in the working tree, plus your own new change) and you need to commit only one of them
- `git add -p` is not usable — no interactive TTY, or the caller cannot answer `y`/`n`/`s` prompts
- The hunks are far enough apart in the file that `git diff -U0` shows them as separate `@@` blocks

## When NOT to Use

- The hunks are adjacent/overlapping (a single `@@` block covers both) — hunk splitting can't separate them; use `git add -p`'s `s` (split) + `e` (manual edit) interactively instead, or a real TTY
- `git add -p` is available and scriptable in the current environment — prefer it, it's the standard tool for this

## Procedure

### Step 0. Identify the target hunk

```bash
git diff -U0 -- <file>
```

`-U0` (zero context lines) prints each hunk as a separate `@@ -old,count +new,count @@` block — confirms your target change is isolated from the unrelated hunk(s).

### Step 1. Extract the base (HEAD) version

```bash
git show HEAD:<file> > /tmp/base.<ext>
```

### Step 2. Reconstruct the target state

Apply only your intended change to a copy of the base — not the working tree, which has both hunks mixed in.

```bash
cp /tmp/base.<ext> /tmp/target.<ext>
# apply only your change, e.g. an insertion after an anchor line:
awk '{print} /<anchor-line-regex>/{print "<your-inserted-line>"}' /tmp/base.<ext> > /tmp/target.<ext>
```

The exact reconstruction mechanism (awk/sed/manual edit) depends on the change shape — insertion, deletion, or modification.

### Step 3. Diff base vs target to get a clean single-purpose patch

```bash
git diff --no-index -- /tmp/base.<ext> /tmp/target.<ext> | \
  sed 's|a/tmp/base.<ext>|a/<file>|; s|b/tmp/target.<ext>|b/<file>|' \
  > /tmp/clean.patch
```

The `sed` rewrites the synthetic `/tmp/...` paths back to the real repo-relative path so `git apply` can target the actual file.

### Step 4. Apply to the index only, verify, commit

```bash
git apply --cached --check /tmp/clean.patch   # dry-run — must exit 0
git apply --cached /tmp/clean.patch
git diff --cached -- <file>                    # confirm exactly your intended lines are staged
git diff -- <file>                             # confirm the OTHER hunk(s) remain unstaged
git commit -m "..."
```

`git apply --cached` writes the patch directly into the index without touching the working tree — the other unstaged hunk(s) stay exactly as they were, ready for a separate commit later.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | `git add <file>` when the file has 2+ unrelated hunks | Isolate the target hunk first (Steps 0-3), then `git apply --cached` only that patch |
| 2 | Hand-write the patch's `@@` header by copying it from `git diff -U3`/`-U0` output | Generate the patch via `git diff --no-index` on reconstructed base/target files — hand-edited hunk headers (line counts) are a common source of `git apply` failures |
| 3 | Skip the `--check` dry-run before `git apply --cached` | Always dry-run first — a failed cached-apply can leave the index in a partially-modified state |
| 4 | Forget to verify the *other* hunk is still unstaged after applying | `git diff -- <file>` after commit — confirm the remaining hunk didn't get silently included |

Clean up temp files after the commit lands.
