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
| `description:` | **Yes** | Description + trigger keywords |

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
