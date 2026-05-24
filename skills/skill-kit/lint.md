# Skill Lint

Validate and fix SKILL.md frontmatter issues automatically.

## Scan Paths

1. `~/.claude/skills/` - Personal skills
2. `~/.claude/plugins/marketplaces/*/plugins/*/skills/` - Plugin skills
3. `.claude/skills/` - Project skills

## Validation Rules

### Common Fields (Ordered)

| Field | Required | Description |
|-------|----------|-------------|
| `name:` | **Yes** | Skill name (must match directory) |
| `description:` | **Yes** | Description + trigger keywords. **Length ≤ 1024 chars** (see below) |

### Description Length Budget (HARD STOP)

**`description` field must be ≤ 1024 characters.** Claude Code's system reminder truncates descriptions beyond the limit, dropping trigger keywords at the tail — which causes skill discovery failures.

**Measure**:

```bash
DESC=$(awk '/^description:/,/^---$/' SKILL.md | sed -E 's/^description: //; /^---$/d' | tr -d '\n')
echo "len: ${#DESC}"
# Expected: ≤ 1024. If over → truncate or split topics.
```

**Reduction strategies (in priority order)**:

| # | Strategy | Example |
|---|----------|---------|
| 1 | Compress `Use when` keyword list | Remove redundant synonyms (e.g., "session ID", "current session", "session id" → keep one) |
| 2 | Shorten topic descriptions to ≤ 40 chars each | `list - enumerate current-project sessions (UUID + mtime + size)` → `list - enumerate sessions` |
| 3 | Drop locale-duplicate keywords | If English and Korean keywords overlap meaning, keep one per concept |
| 4 | Move detail to topic .md files | Topic .md files are unbounded — push verbose explanations there, keep description terse |

**Don't / Do table (HARD STOP — derived from 5 cumulative violators 2026-05-23)**:

| # | Don't (overweight pattern) | Do (canonical compression) | Real violation case |
|---|---------------------------|---------------------------|---------------------|
| 1 | Append new topic description without measuring current length | `wc -c` or awk-length check before Edit; if `current + new > 1024`, compress first | claude-session: 1480 → 1547 over limit |
| 2 | Locale-mix in description (English skill with non-English keywords, or vice versa) | Single locale only. **English skill = 0 non-English keywords**. Non-English skill = native keywords primary, English allowed only for proper nouns/technical terms (Vault, ArgoCD, K3s, etc.). See `opensource.md` "Skill language = description language" HARD STOP | ralph: an English keyword paired with two transliterated synonyms (`"ralph update"+"ralph <update-localized>"+"ralph <latest-localized>"`) → If ralph is an English skill, keep only the English form. If localized, keep only one localized form. No mix. |
| 3 | Multiple English synonym variants for the same action | One canonical verb + one canonical noun. No `"X fix"+"fix X"+"update X"+"modify X"` chains | skill-kit: `"skill upgrade"+"skill fix"+"fix skill"+"update skill"` → `"skill upgrade"` only |
| 4 | Topic description over 40 chars or with Step numbers / parenthetical context | Topic description = `<topic> - <one-liner ≤ 40 chars>`. Move Step numbers / nested context to topic .md | consolidate: `internal - Step 3.5 Internal Code Review fallback (CodeRabbit Free walkthrough only / Copilot failure) + Step 4.5 UI capture verification` → `internal - CodeRabbit fallback review` |
| 5 | Append `[filename.md]` to topic descriptions | Topics table already has the file path. description has topic + one-liner only | github-flow: 8x `[xxx.md]` removed (~100 chars saved) |
| 6 | Verbose prose context inside description (full sentences, "Applies to..." paragraphs) | description = one-line skill purpose + topic enumeration + Use when. Prose belongs in topic .md or SKILL.md body | code-workflow: `Applies to all tasks requiring code changes... TDD (Red→Green→Refactor) is applied by default... For GitHub repos, github-flow is the default companion...` → removed (~300 chars saved) |
| 7 | Localized keyword conjugation variants (multiple inflections of the same concept, e.g. "tidy"+"sync"+"items" all referring to the same fix_plan operation) | One canonical conjugation per concept (usually `noun + verb-stem` or a single verb) | ralph: 5 conjugated variants of "fix_plan tidy/sync/items/done-move/Completed-move" → keep only `"fix_plan tidy"` (one canonical form). The unused variants were inflectional duplicates of the same intent |
| 8 | Mix other frontmatter fields (`allowed-tools:`, `depends-on:`) into description text | Each YAML field on its own line. description ends before next field | consolidate: `triggers.allowed-tools: [Agent...]depends-on: [superpowers]` mixed into description tail — separate to own fields |
| 9 | Trust system reminder display ("looks fine to me") | System reminder truncates with `…`. Always measure with `wc` or awk every Edit | claude-session: `"sess…"` truncate confirmed in system reminder |

**Self-check (every time before Edit on `description:` field)**:
1. Measure current length (`awk + tr -d '\n' + ${#}` pattern)
2. Estimate new length after Edit
3. If `> 1024`, apply reduction strategies #1~4 + Don't/Do patterns #1~9 first
4. Re-measure after Edit. Confirm ≤ 1024
5. Verify Topics table is the authoritative source for `[filename.md]` references — description should NOT repeat them

**Violation cases (cumulative — system-wide non-compliance)**:
- 2026-05-23 (1st flagged): `claude-session` 1547 chars after `list` topic added → user pointed it out
- Pre-existing violations (cumulative): `github-flow` 2116, `ralph` 1506, `code-workflow` 1269, `consolidate` 1187, `skill-kit` 1091 — all over 1024. Strengthen this rule + run `/skill-kit lint --fix` across skills to bring under limit

### Invalid Fields

| Invalid | Correct | Action |
|---------|---------|--------|
| `tools:` | `allowed-tools:` | Rename field |
| `trigger:` | (remove) | Move keywords to description |
| `triggers:` | (remove) | Move keywords to description |
| `<example>` in description | (remove) | `<example>` is agent-only syntax. Remove from skills. |

### Frontmatter Field Order (Canonical Order)

Frontmatter fields follow this order for readability. lint --fix will reorder automatically.

```yaml
---
name:                      # 1. Required
depends-on:                # 2. Dependencies
triggers:                  # 3. Hook triggers
description:               # 4. Required (last among required - longest)
allowed-tools:             # 5. Optional
agent:                     # 6. Optional
context:                   # 7. Optional
hooks:                     # 8. Optional
model:                     # 9. Optional
user-invocable:            # 10. Optional
---
```

**Order validation rules:**
- Warn if required fields (name, description) appear between optional fields
- depends-on must follow immediately after name
- triggers must follow immediately after description
- Optional fields should be in alphabetical order among themselves

### Valid Optional Fields

```yaml
agent: general-purpose     # Agent type
allowed-tools: [...]       # Tool restrictions
context: fork              # Context handling
depends-on: [skill-a, skill-b]  # Dependent skill list
hooks: {...}               # Hook configuration
model: claude-sonnet-4-... # Specific model
triggers: [...]            # Hook trigger declarations
user-invocable: true       # User can invoke directly
```

### Description Rules

- Max 1024 characters
- Include "what it does" + "when to use"
- Natural trigger keywords

## Workflow

### Step 0: External Validation (skills-ref CLI — Anthropic official)

Before applying the custom rules below, run Anthropic's official reference validator `skills-ref` if available. It enforces the upstream Agent Skills spec (name / description / frontmatter shape) — independent of the custom checks in this file.

#### 0a. Check availability

```bash
if command -v skills-ref >/dev/null 2>&1; then
  skills-ref --version
  SKILLS_REF_AVAILABLE=1
else
  SKILLS_REF_AVAILABLE=0
fi
```

#### 0b. Available — run validate

```bash
# Single skill
skills-ref validate ~/.claude/skills/<skill-name>

# All personal skills
for d in ~/.claude/skills/*/; do
  [ -f "$d/SKILL.md" ] || continue
  echo "=== $(basename "$d") ==="
  skills-ref validate "$d"
done
```

Treat any reported problem as a blocking issue. Re-run until the output is empty before proceeding to Step 1.

Properties readout (useful for cross-referencing the Topics table):

```bash
skills-ref read-properties ~/.claude/skills/<skill-name>   # JSON: name, description, ...
```

#### 0c. Not available — install

If `command -v uv` succeeds:

```bash
uv tool install "git+https://github.com/agentskills/agentskills.git#subdirectory=skills-ref"
```

After install, `skills-ref` is on PATH (`~/.local/bin/skills-ref`) — no alias needed. Re-run Step 0a to confirm, then 0b.

If `uv` is missing:

| Platform | Install uv |
|----------|------------|
| macOS | `brew install uv` |
| Linux | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Windows (PowerShell) | `irm https://astral.sh/uv/install.ps1 \| iex` — runs in user scope, no elevation needed |

If neither `uv` nor a viable installer is available in the current environment, **skip Step 0 and proceed with Step 1** — the custom rules below provide partial coverage only (description-length budget, depends-on order, hardlink scan), not the upstream spec enforcement. **Report the skip explicitly** with a risk statement naming which upstream checks were not exercised (e.g., "Step 0 skipped — `skills-ref` name-match and properties-JSON validation not run").

#### 0d. Upgrade

```bash
uv tool upgrade skills-ref
```

#### Why both layers

| Validator | Strengths |
|-----------|-----------|
| `skills-ref` (upstream) | Authoritative spec enforcement (name match, description shape, properties JSON read); tracks Anthropic's reference implementation |
| Custom rules (Steps 1–4 below) | Description length budget (1024), depends-on alphabetical order, hardlink-aware scan, plugin/project skill paths |

The two are complementary — run both. `skills-ref` failures must be fixed before the custom rules can be trusted.

### Step 1: Scan for Issues

```bash
# Missing required fields
find ~/.claude/skills -name "SKILL.md" ! -path "*.bak*" -exec sh -c \
  'head -10 "$1" | grep -q "^name:" || echo "name missing: $1"' _ {} \;

find ~/.claude/skills -name "SKILL.md" ! -path "*.bak*" -exec sh -c \
  'head -10 "$1" | grep -q "^description:" || echo "description missing: $1"' _ {} \;

# Invalid fields
grep -r "^triggers:" ~/.claude/skills --include="SKILL.md" | grep -v ".bak"
grep -r "^tools:" ~/.claude/skills --include="SKILL.md" | grep -v ".bak"

# Frontmatter position (must start on line 1)
find ~/.claude/skills -name "SKILL.md" ! -path "*.bak*" -exec sh -c \
  'head -1 "$1" | grep -q "^---$" || echo "frontmatter position error: $1"' _ {} \;
```

### Step 2: Report Issues

| File | Issue | Fix Required |
|------|-------|--------------|
| skill-a/SKILL.md | name: missing | Add name to frontmatter |
| skill-b/SKILL.md | triggers: used | Remove, add to description |
| skill-c/SKILL.md | tools: used | Change to allowed-tools: |

### Step 3: Fix (with user confirmation)

#### Missing Frontmatter

**Before:**
```markdown
# My Skill

Description here.
```

**After:**
```yaml
---
name: my-skill
description: Description here. "keyword1", "keyword2" triggers
---

# My Skill
```

#### triggers: → description

**Before:**
```yaml
---
name: my-skill
description: Does something useful
triggers:
  - keyword1
  - keyword2
---
```

**After:**
```yaml
---
name: my-skill
description: Does something useful. "keyword1", "keyword2" triggers
---
```

#### tools: → allowed-tools:

**Before:**
```yaml
tools:
  - Read
  - Bash(git:*)
```

**After:**
```yaml
allowed-tools: [Read, Bash(git:*)]
```

### Step 4: Validate

```bash
head -20 SKILL.md  # Check YAML syntax
```

## Dependency Validation (depends-on + external references)

### Step A: depends-on field validation

**Checks:**
1. Verify each listed skill actually exists
2. **Alphabetical order** — `[chezmoi, skill-manager, utcp]` (OK), `[utcp, chezmoi, skill-manager]` (NOT OK)

Auto-sort if not in alphabetical order:

```bash
# Extract depends-on from all SKILL.md → verify skill existence
for skill_md in ~/.claude/skills/*/SKILL.md; do
  deps=$(grep "^depends-on:" "$skill_md" | sed 's/depends-on: *\[//;s/\]//;s/,/ /g')
  for dep in $deps; do
    dep=$(echo "$dep" | tr -d ' "'"'"'')
    [ -z "$dep" ] && continue
    if [ ! -d ~/.claude/skills/"$dep" ] && [ ! -d .claude/skills/"$dep" ]; then
      echo "BROKEN: $(dirname $skill_md | xargs basename) depends-on '$dep' — not found"
    fi
  done
done
```

### Step B: Skill reference validation in rules/PROMPT.md

Extract `/skill-name` or `Skill("skill-name"` patterns from rules, PROMPT.md, and skill topic files, then verify each referenced skill exists:

```bash
# Scan targets: ~/.agent/rules/*.md, .ralph/PROMPT.md, ~/.claude/skills/*/*.md
SCAN_PATHS="$HOME/.agent/rules/*.md .ralph/PROMPT.md $HOME/.claude/skills/*/*.md"

# /skill-name pattern (slash command references)
grep -hoP '(?<=/)[a-z][-a-z0-9]+' $SCAN_PATHS 2>/dev/null | sort -u | while read ref; do
  if [ ! -d ~/.claude/skills/"$ref" ] && [ ! -d .claude/skills/"$ref" ]; then
    echo "BROKEN_REF: /$ref — skill not found"
  fi
done

# Skill("name" pattern (Skill tool invocations)
grep -hoP 'Skill\("([^"]+)"' $SCAN_PATHS 2>/dev/null | sed 's/Skill("//;s/"//' | sort -u | while read ref; do
  if [ ! -d ~/.claude/skills/"$ref" ] && [ ! -d .claude/skills/"$ref" ]; then
    echo "BROKEN_REF: Skill(\"$ref\") — skill not found"
  fi
done
```

### Step C: Report format

| Source file | Reference | Status |
|-----------|------|------|
| `ralph/SKILL.md` | `depends-on: safe-delete` | OK / BROKEN |
| `rules/file-operations.md` | `/safe-delete` | OK / BROKEN |
| `.ralph/PROMPT.md` | `Skill("safe-delete")` | OK / BROKEN |

## Related Actions

After lint completes, recommend:

### Duplicates Found?

If skills with similar names/descriptions exist:

```
💡 Found potential duplicates. Run dedup?
   /skill-manager dedup
```

### Multiple Related Skills?

If skills share a common prefix (e.g., `k8s-deploy`, `k8s-debug`):

```
💡 Related skills detected. Consider merging?
   /skill-manager merge k8s-deploy k8s-debug
```

## Auto-fix Rules

1. **triggers array → description string**
   - Convert to `"keyword1", "keyword2" triggers` format
   - Append to description

2. **tools → allowed-tools**
   - Rename field only, keep values

3. **Multi-line description cleanup**
   - Convert `|` block scalar to single line
   - Remove internal triggers: text

## Example

### Input (invalid)

```yaml
---
name: example-skill
description: |
  Example skill for demo
  triggers:
    - example
    - demo
tools:
  - Read
  - Edit
---
```

### Output (fixed)

```yaml
---
name: example-skill
description: Example skill for demo. "example", "demo" triggers
allowed-tools: [Read, Edit]
---
```

## Notes

- `.bak` directories are excluded from scans
- Always confirm before fixing
- For plugin skills, consider contributing fixes upstream
