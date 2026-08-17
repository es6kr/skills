# Language — Skill language = SKILL.md frontmatter `description` language (HARD STOP)

**Every skill file (SKILL.md, topic .md, resources/*) is written in the same language as the SKILL.md frontmatter `description` field.** If description is English, all topic and resource files are English; if Korean, all are Korean. No per-Edit publish-target matching needed — the frontmatter description line alone decides.

**`description` field itself must be a single language (HARD STOP)**. English skills allow **zero Korean keywords** in description (including trigger keywords). Korean skills may include English technical terms (Vault, ArgoCD, K3s, etc.) but the main description prose is Korean. No "mixed" exception.

| Skill language (per description first sentence) | description body | description trigger keywords |
|------|------|------|
| English skill | English only | English only (zero Korean keywords) |
| Korean skill | Korean only | Korean primary + English allowed only for proper nouns/technical terms (e.g., "Vault", "ArgoCD") |

## Don't / Do table (description itself)

| # | Don't | Do |
|---|-------|-----|
| A | Add any non-English trigger keyword to an English skill's description (e.g., adding a Korean translation/synonym of an existing English keyword) | Use English-only trigger keywords. Non-English users can still match via the English keywords |
| B | "Adding just one Korean keyword lets Korean users trigger the skill" thinking | The system reminder exposes the full description to English speakers too. Even one Korean keyword breaks description consistency + wastes the truncate budget |
| C | locale-duplicate with "core nouns are OK" (the previous weak lint.md rule) | English skill = zero Korean. Even a core noun applicable to both locales gets one English keyword only |
| D | Korean skill description lists English trigger keywords with equal weight | Korean skills keep Korean keywords as primary. English is restricted to proper nouns/technical terms |

## Don't / Do table (skill body)

| # | Don't | Do |
|---|-------|-----|
| 1 | Match against publish target / LICENSE presence / skill catalog before Edit | Check the SKILL.md first line `description:` language → write in that language |
| 2 | "It's a mixed file, so it's ambiguous" thinking | frontmatter description is the primary criterion. Even if Korean sections exist in the body, the description language is the enforced answer |
| 3 | "Existing Korean is there, so new additions can be Korean too" | If description is English, existing Korean is a mistake. Write new additions in English + queue existing Korean for a separate English conversion task |

## Self-check (every time before editing a skill file)

1. Confirm the description line with `head -5 <SKILL.md>` or `Grep "^description:" <SKILL.md>`
2. description in English → write English. In Korean → write Korean
3. If the body is mixed, the description language is the source of truth (mixed = partial stale signal)
4. **Prior-task language ≠ skill description language — self-check (HARD STOP — prevents recurrence)**: Even if the prior N actions (e.g., posting a Korean PR correction comment / updating a Korean fix_plan / posting a Korean inline review) were all in Korean, if the skill file's description language is English, write in English. "Context inertia" is the most common bypass pattern

## Context inertia trap (HARD STOP)

| # | Don't | Do |
|---|-------|-----|
| 1 | Write the new skill section in the same language as the prior N actions | Re-check the description before any skill Edit → reset every Edit (prior task language is irrelevant) |
| 2 | "PR comment was Korean, fix_plan was Korean, inline review was Korean → skill addition is Korean too" mapping | Per-medium language rules are independent: medium language (PR / fix_plan / inline) is decided separately from skill file language |
| 3 | "Body has one Korean section already, so mixing is fine" rationalization | A Korean section in the body = stale signal. description language is the answer. New additions follow description language |
| 4 | "Just this one section in Korean, will convert to English later" deferral | Write in English at addition time. Deferral = permanent mix + higher cleanup cost |

**Self-check trigger keywords** (re-check description before every skill Edit if any of these apply):

- The prior response wrote/posted Korean text (PR comment, fix_plan entry, inline review body, etc.)
- The prior response wrote/posted English text (GitHub PUBLIC repo issue/PR body, etc.)
- The Edit target file path contains "skills/", `~/.claude/skills/`, or `~/.agents/skills/`
- new_string contains a markdown section (`###`, `####`, `|` table)

## Exceptions

- Korean skill description's **proper nouns / technical terms** (Vault, ArgoCD, K3s, Authentik, etc.) — keep English as-is
- English skill description's **proper nouns / product names** (no Korean transliteration/translation added)
- description must be single-language (mixing deprecated)
- If a description language change is needed, decide separately (per skill publish policy)

## Hook installed

- Script: `~/.agents/skills/hook-kit/resources/edit-guard.sh` — function `check_skill_language_mismatch()` (consolidated from the retired standalone `block-skill-language-mismatch.sh`, now in `~/.claude/.bak/`)
- Registration: PreToolUse:Edit and PreToolUse:Write matchers in `~/.claude/settings.json` reference `edit-guard.sh` directly (no separate install copy)
- Scope: only `.md` files under `*/skills/<name>/`. Code/data files unaffected
- Detection: zero Hangul in SKILL.md `description` → strict mode (any Hangul in `NEW_CONTENT` → DENY exit 2). Hangul in description → permissive (Korean skills may include English technical terms)
- Quote handling: user quotes must be paraphrased into English before pasting into English skill files. The hook does not distinguish quote vs body content

### Untracked-file audit gap (HARD STOP for hook migration)

`check_skill_language_mismatch()` fires only at PreToolUse:Edit/Write — it does not scan pre-existing untracked files. A file written under a **hook migration gap** (old standalone retired → new consolidation not yet active) persists indefinitely as untracked Korean in an English skill dir. Detect and remediate via:

1. Any hook migration (retiring or renaming a guard hook) must **grep the replacement location for the guard function/logic** before retiring the old script. Emit the grep result in the migration commit body
2. `check-hangul.py` `.md` scan already covers untracked files at commit time — but only when at least one file in the same skill dir is staged, so orphan untracked drift can persist across sessions
3. Session-start or periodic audit — enumerate every English skill dir and grep newer-than-`SKILL.md` `.md` files for the Hangul range U+AC00–U+D7A3 (the range used by `check_skill_language_mismatch` in `edit-guard.sh`). Any match = drift candidate for review

## PUBLIC repo locale-pattern externalization — `data/` folder (HARD STOP)

When a PUBLIC repo skill needs Korean detection regex or locale-specific keyword matching (e.g., a Hangul-text-detection hook, Korean keyword alternation), **do NOT inline it in the skill body**. Externalize to **`<skill>/data/*.regex`**.

### Why

- PUBLIC repos enforce English (the repository language rule + `check-hangul` lint)
- But some hooks must detect Korean phrasing in user input (e.g., Korean keywords for merge/issue/complete) to function
- Inlining gets blocked by lint. An `# check-hangul: allow` inline marker still leaves Korean in the PUBLIC repo — not a clean solution
- `data/` folder registered in `.gitignore` + `.clawhubignore` → **zero Korean in PUBLIC repo**, locale data preserved locally

### Don't / Do

| # | Don't | Do |
|---|-------|----|
| 1 | Inline Korean detection regex in hook body (`*.sh`/`*.md`) → `check-hangul` blocked | Externalize locale data to `data/*.regex` + hook `source`s it at runtime |
| 2 | `# check-hangul: allow` inline marker to bypass lint (Korean still in PUBLIC) | data/ externalization (zero Korean in PUBLIC) |
| 3 | Leave `data/` unregistered in `.gitignore` → tracked and pushed to PUBLIC | Register `data/` in both `.gitignore` and `.clawhubignore` |
| 4 | Hook crashes on missing data file (`unbound variable`) | `${VAR:-english-default}` fallback — silent no-op or English-only matching when locale data absent |
| 5 | Use `.sh` / `.md` extension for data file → scanned by `check-hangul` | Use `.regex` / `.txt` / `.conf` or any extension outside `SCAN_EXTS` |

### Self-check (before adding/modifying a hook in a PUBLIC skill)

1. Does the hook contain Korean detection regex or locale-specific keywords?
2. Yes → separate to `<skill>/data/<purpose>.regex`. Confirm `data/` registered in `.gitignore` + `.clawhubignore`
3. Hook uses `. "$HG_DATA_FILE"` to source + `${VAR:-english-default}` fallback
4. Verify `python3 scripts/check-hangul.py skills/<skill>` passes (zero matches)
5. Confirm data file does not appear in `git status --short skills/<skill>/`

