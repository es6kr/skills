# Skill Writer

Create well-structured Agent Skills for Claude Code with proper validation.

## When to Use

- Creating a new Agent Skill
- Writing or updating SKILL.md files
- Converting existing prompts/workflows into Skills
- Troubleshooting skill discovery issues

## Instructions

### Step 1: Determine Skill Scope

Ask clarifying questions:
- What specific capability should this Skill provide?
- When should Claude use this Skill?
- What tools or resources does it need?
- Is this for personal use or team sharing?

**Keep it focused**: One Skill = one capability
- Good: "PDF form filling", "Excel data analysis"
- Too broad: "Document processing", "Data tools"

**Language rule**: Skills intended for distribution (ClawHub, plugins) must be written in **English** — SKILL.md frontmatter, headings, and body. Personal-only skills may use any language.

### Step 2: Choose Location

| Location | Purpose |
|----------|---------|
| `~/.claude/skills/` | Personal skills |
| `.claude/skills/` | Project skills (committed to git) |

### Step 3: Create Structure

```bash
mkdir -p ~/.claude/skills/skill-name
```

For multi-file Skills:
```
skill-name/
├── SKILL.md (required)
├── reference.md (optional)
├── examples.md (optional)
└── scripts/ (optional)
```

For multi-topic Skills, see [architecture.md](./architecture.md).

### Step 3.5: Detect Language

When adding topics to an existing skill, match the language of the existing content:

1. Read the existing `SKILL.md` and 1-2 topic files
2. If content is **English** → write new topic in **English only**
3. If content is **Korean** → write in **Korean** (technical terms in English OK)
4. If mixed → follow the **majority language**

**Do not** write Korean content in an English skill or vice versa.

### Step 4: Write Frontmatter

```yaml
---
name: skill-name
description: Brief description of what this does and when to use it
---
```

**Field requirements**:

- **name**: lowercase, hyphens only, max 64 chars, must match directory name
- **description**: max 1024 chars, include "what" AND "when to use"

**Optional fields**:
```yaml
allowed-tools: [Read, Grep, Glob]  # Restrict tool access
model: claude-sonnet-4-...         # Specific model
context: fork                       # Context handling
```

### Step 5: Write Effective Descriptions

**No `<example>` blocks**: Do not put `<example>` blocks in SKILL.md frontmatter. `<example>` is agent-only syntax (`.claude/agents/*.md`). Skills match via description text and trigger keywords only.

**Formula**: `[What it does] + [When to use it] + [Key triggers]`

✅ **Good**:
```yaml
description: Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.
```

❌ **Too vague**:
```yaml
description: Helps with documents
```

**Tips**:
- Include specific file extensions (.pdf, .xlsx, .json)
- Mention common user phrases ("analyze", "extract", "generate")
- Add context clues ("Use when...", "For...")

### Step 6: Structure Content

```markdown
# Skill Name

Brief overview.

## Quick Start

Simple example to get started.

## Instructions

Step-by-step guidance:
1. First step with clear action
2. Second step with expected outcome

## Examples

Concrete usage examples.

## Requirements

Dependencies or prerequisites.

## Requirements

Dependencies or prerequisites.
```

### Step 7: Validate

Checklist:
- [ ] SKILL.md exists in correct location
- [ ] Directory name matches frontmatter `name`
- [ ] Opening `---` on line 1
- [ ] `name` follows naming rules
- [ ] `description` is specific and < 1024 chars
- [ ] Clear instructions for Claude
- [ ] Concrete examples provided

### Step 8: Test

1. Restart Claude Code to load the Skill
2. Ask relevant questions that match the description
3. Verify activation and behavior

## Common Patterns

### Read-only Skill

```yaml
---
name: code-reader
description: Read and analyze code without changes. Use for code review or documentation.
allowed-tools: [Read, Grep, Glob]
---
```

### Script-based Skill

```yaml
---
name: data-processor
description: Process CSV/JSON data files. Use when analyzing or transforming datasets.
---

## Instructions

1. Run: `python scripts/process.py input.csv`
```

## Troubleshooting

**Skill doesn't activate**:
- Make description more specific with trigger words
- Include file types and operations
- Add "Use when..." clause

**Multiple Skills conflict**:
- Make descriptions more distinct
- Use different trigger words

## Output

When creating a Skill:
1. Ask clarifying questions
2. Suggest name and location
3. Create SKILL.md with proper frontmatter
4. Include instructions and examples
5. Validate against requirements
