# Active PreToolUse:AskUserQuestion Hook Matrix

Reference data for AskUserQuestion callers — pre-check option label/description against active hook block triggers before calling, to avoid block→edit→retry cascades.

## Matrix

| Hook | Block trigger pattern | Pass condition |
|------|----------------------|----------------|
| `block-merge-without-review.sh` | `merge` / `Merge` / `Squash` combined with `PR #N` | Option description must include `AI Review Summary posted (<URL>)` or `AI Review Summary ✅` **AND** `Test Plan N/N ✅` (or `Test Plan all [x]`) |
| `block-tasklist-id-in-conversation.sh` | `#NN` standalone (without PR/issue prefix) | Use `PR #NN` / `issue #NN` prefix or subject keyword (e.g., "Web-PR-346 verification") |
| `block-vendor-in-generic-skill.sh` | Vendor name (qdrant / chroma / pinecone / mcp__\<vendor>__ / private IPs `192.168.*`, `10.0.*`) | Use abstract terms (`RAG store`, `<private-IP>`, `<internal-host>`), or have the vendor name in the immediately preceding user message |
| `block-skill-language-mismatch.sh` | Korean text added to a skill body whose SKILL.md description is English (`.md` Edit) | Write in English, or include explicit citation rationale |
| `block-axis-merged-ask.sh` | Same-category findings (Refactor/Tip/Minor, etc.) collapsed into a single question with N options | Use multi-select question for "select items to process" + separate question for processing method |
| `block-manual-delegation-without-automation-check.sh` | Option label/description contains manual-delegation keyword (`manual` / `Console UI` / `browser to access` / `paste-token` and Korean equivalents) | Include automation-skill evidence in the same description: `<web-browser \| Playwright \| chrome-devtools \| wmux>` paired with `<unavailable \| disconnected \| tried \| failed \| login wall>` (or `no automation applicable — <reason>`) |

(Matrix reflects matchers registered in `~/.claude/settings.json` `PreToolUse:AskUserQuestion`. Update this file when matchers change.)

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Compose options and call AskUserQuestion without pre-grep → block → partial fix → retry cascade | Before calling, grep label + description against the matrix above; on match, apply the pass condition |
| 2 | Quote the hook script name itself (e.g., `block-merge-without-review.sh`) in description → self-match block | Use abstract terms ("review gate guard", "merge guard hook") when referencing a hook |
| 3 | Add only partial pass-condition keywords after a block (e.g., "AI Review Summary posted" without URL) → re-block | Satisfy the full pass condition — `AI Review Summary posted (<URL>)` **and** `Test Plan N/N ✅` |
| 4 | Worktree/branch name contains a vendor (`feat-code-workflow-qdrant`) and is pasted verbatim into option description → block-vendor block | Reference worktrees abstractly ("this PR's head-branch worktree") or cite that the user explicitly named it in the immediately preceding message (caller-side intent) |
| 5 | Treat "block avoidance" as the goal = strip important info from description | If the pass condition genuinely conflicts with the information you need to convey, the block itself is a signal — reassess whether the ask is appropriate (e.g., if AI Review Summary really is absent, a merge option is itself a rule violation) |

## Self-check (before every AskUserQuestion call)

1. Visually grep the entire label + description against the 6 hook block patterns above
2. On match → add the pass-condition keyword to description, or rewrite with abstract terms
3. **Block avoidance = information-loss signal**: if failing the pass condition implies the ask itself is inappropriate (e.g., proposing a merge option when Test Plan isn't N/N), re-evaluate the ask itself rather than working around it
4. One block cascade = signal the self-check was skipped. From the second cascade onward, re-read this matrix file

## Procedure

1. After drafting the AskUserQuestion options array
2. Iterate the 6 hook block patterns above and grep
3. Fix matched options' description (add pass-condition keyword or abstract)
4. Re-grep after fixes — confirm 0 matches before calling
5. If a block still occurs after calling = this matrix is missing an entry → update (new hook may have been added to settings.json)

## Exceptions

- Hook false positive (caller-side intent is clear — e.g., user just named the vendor in the preceding message): cite the caller-side intent in description and call. `block-vendor-in-generic-skill.sh` honors a "user explicitly asked" exemption
- `block-merge-without-review.sh` pass-condition keywords must match the real PR state (Critical 0, CI pass, Test Plan complete). If the state is fabricated to pass the gate, the ask itself is inappropriate

## Violation history

See `~/.claude/skills/cleanup/data/failed-attempts.md` "active hook keyword pre-check" entries.
