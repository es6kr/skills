# Diff Required — verify chezmoi apply / modify-script edits with diff (AskUserQuestion mandatory)

## Diff required before every apply

**Every `chezmoi apply` invocation must first show a `chezmoi diff` to the user and receive explicit approval.**

- Run `chezmoi diff` → review the output → call `AskUserQuestion` for approval → `chezmoi apply`
- If the diff output is empty (no changes), skip the apply

**Forbidden**:
- `chezmoi apply` without a preceding diff
- Running the diff but skipping the step where the user sees it

**Correct procedure**:
1. Run `chezmoi diff`
2. Summarize the file list and change contents
3. `AskUserQuestion` — "Apply these changes?"
4. On approval, run `chezmoi apply`

## Diff required when modify-scripts are edited

**After editing files under `.chezmoi-lib/` or `modify_*.sh.tmpl`, run `chezmoi diff` and show it to the user before applying.**

Edits to a modify-script change the final rendered output of its target files. The diff is the only way to see that effect before landing it.

**Correct procedure**:
1. Edit `.chezmoi-lib/*.sh` or `modify_*.sh.tmpl`
2. Run `chezmoi diff <target-file>` — confirms the actual output effect of the script edit
3. Show the diff to the user
4. `AskUserQuestion` for approval
5. On approval, run `chezmoi apply`

**Forbidden**:
- Applying after a script edit without any diff
- Skipping the diff on the assumption "only the script changed, the result must be identical"
- Running the diff but withholding it from the user, then applying

**External edits (user or linter) trigger the same procedure (HARD STOP)**: When a system reminder announces `Note: <modify-script-path> was modified` — regardless of the author (AI / user / linter) — **immediately run `chezmoi diff <target-file>` and report the result**. Do not conclude "the user did this on purpose, no follow-up needed." The obligation to verify the rendered output of the change stays with the calling AI.

**User statements about chezmoi config changes trigger the same procedure (HARD STOP)**: `~/.config/chezmoi/chezmoi.toml` is not a managed file, so no system reminder fires when it changes. When the user's message signals a *chezmoi data section change* (e.g., "I edited chezmoi.toml", "added a variable", "changed the config", "flipped statusline_type") — even without a system reminder — **immediately run `chezmoi diff` on the affected modify targets**. When you cannot tell which section of chezmoi.toml was touched, either run `chezmoi diff` with no arguments (all managed files) or diff a small set of the most likely target files.
