# Isolate Hunk

Stage only your own edit to a tracked file whose working tree copy also carries unrelated uncommitted content — without touching that other content at all.

## When to use

- The repo is a shared skills monorepo and another session/device has concurrent work-in-progress in a file you also need to edit
- `git status` shows the file as modified, but `git diff` reveals hunks you never wrote mixed in with your own
- You need to commit and PR your change now, without waiting for the other work to land or reviewing it yourself

Naive `git add <path>` would stage the entire working-tree file, bundling the unrelated content into your commit. This topic isolates just your hunk.

## Procedure

### 1. Identify which hunks are yours

```bash
git -C <repo> diff <path>
```

Read every hunk. A hunk is **yours** only if you made that exact edit this session (via Edit/Write). Anything else — even if it looks plausible — belongs to whoever else is working on the file.

If unsure whether a hunk is yours, check its content against what you actually wrote (your Edit tool call's `old_string`/`new_string`), not against what "looks right."

### 2. Extract the HEAD baseline and your intended content

```bash
git -C <repo> show HEAD:<path> > /tmp/base.md
```

Build a target file = HEAD baseline + only your insertion(s), anchored on surrounding text you can locate exactly in the baseline. This step is inherently manual — it depends on knowing your own edit's exact anchor and inserted text, not something a generic script can infer.

A safe way to build the target programmatically (avoids shell quoting issues with multi-line Markdown content):

```python
head = open("/tmp/base.md", encoding="utf-8").read().splitlines(keepends=True)
anchor = "<exact line from the baseline that precedes your insertion>\n"
idx = head.index(anchor)
my_insertion = "<your exact inserted lines>\n"
target = head[:idx+1] + my_insertion.splitlines(keepends=True) + head[idx+1:]
open("/tmp/target.md", "w", encoding="utf-8", newline="").writelines(target)
```

### 3. Verify the target contains only your change

```bash
diff /tmp/base.md /tmp/target.md
```

Every line in this diff should be something you recognize as your own edit. If anything unexpected appears, the anchor or insertion text was wrong — fix it before continuing.

### 4. Stage the isolated content

```bash
scripts/stage-isolated-content.sh <repo> <path> /tmp/target.md
```

This creates a git blob from `/tmp/target.md` and points the index entry for `<path>` at it — the working tree file (still containing the other session's untouched content) is never modified.

### 5. Commit and verify the working tree is untouched

```bash
git -C <repo> commit -m "<type>(<scope>): <summary>"
git -C <repo> diff <path>   # should show the SAME unrelated hunks as before — proof nothing was disturbed
```

The post-commit `git diff` should show exactly the other session's content as still-uncommitted — confirming your commit captured only your change and left everything else in place.

## Repeat for multiple files

If several files each mix your edits with unrelated content, run steps 1-4 for each file before committing — `git commit` picks up everything currently staged in one pass. Unstage a file (`git reset <path>`) if you want it in a separate commit instead.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | `git add <path>` when the working tree mixes your edit with someone else's uncommitted content | Build an isolated target (steps 2-3) and stage it via `stage-isolated-content.sh` |
| 2 | Assume a hunk is "probably fine to include" because it looks reasonable | Only include hunks you can trace to your own Edit/Write calls this session |
| 3 | Revert or overwrite the other session's working-tree content to "clean up" before committing | Never touch working-tree content you didn't write — the whole point of this technique is to leave it untouched |
| 4 | Skip the post-commit `git diff` check | Always verify the other content is still present and unstaged after your commit |

## Self-check (before running `stage-isolated-content.sh`)

1. Did you read every hunk in `git diff <path>` and classify each as yours or not?
2. Does your target file's diff against HEAD (step 3) contain only lines you recognize as your own edit?
3. After staging, does `git show :<path>` match your target file exactly?
4. After committing, does `git diff <path>` still show the other session's hunks as uncommitted (proof the working tree was never touched)?
