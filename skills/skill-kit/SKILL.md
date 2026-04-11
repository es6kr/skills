---
name: skill-kit
description: Claude Code skill management. writer - create new skills [writer.md], lint - validate and fix frontmatter [lint.md], merge - combine related skills [merge.md], dedup - find duplicate skills [dedup.md], convert - convert agents to skills [convert.md], architecture - multi-topic skill structure [architecture.md], upgrade - enhance existing skills, add topics [upgrade.md], route - recommend topic placement [route.md], trigger - declare SKILL.md triggers - auto-generate and register hooks [trigger.md]. Use when "skill writer", "skill lint", "skill merge", "skill dedup", "create skill", "frontmatter fix", "combine skills", "multi-topic skill", "agent to skill", "convert agent", "skill improve", "skill upgrade", "skill fix", "fix skill", "update skill", "add topic", "topic routing", "topic placement", "where to put", "topic route", "trigger compile", "compile triggers", "hook auto register", "trigger list".
---

# Skill-Kit

Comprehensive toolkit for creating, managing, and maintaining Claude Code skills.

## Commands

| Command | Description | Link |
| ------- | ----------- | ---- |
| architecture | Multi-topic skill structure and topics | [architecture.md](./architecture.md) |
| convert | Convert agents or scripts to skills | [convert.md](./convert.md) |
| dedup | Identify and merge duplicate skills | [dedup.md](./dedup.md) |
| lint | Validate and fix SKILL.md frontmatter | [lint.md](./lint.md) |
| merge | Combine related skills into one | [merge.md](./merge.md) |
| route | Recommend topic placement within skills | [route.md](./route.md) |
| trigger | Register triggers and generate hooks | [trigger.md](./trigger.md) |
| upgrade | Enhance existing skills or add topics | [upgrade.md](./upgrade.md) |
| writer | Interactive skill creation wizard | [writer.md](./writer.md) |

## Core Workflows

### Creation (skill-writer)

Always use `writer` to ensure correct frontmatter and structure.

```bash
/skill-kit writer                  # Start wizard
```

### Maintenance (upgrade/lint)

Use `upgrade` to add new functionality or topics to an existing skill.

```bash
/skill-kit upgrade skill-name      # Interactive upgrade
/skill-kit lint skill-name         # Validation only
```

Improvement types:
- **Add Topic**: Add documentation for a new sub-feature
- **Add Script**: Add logic to `scripts/` and reference in SKILL.md
- **Fix Frontmatter**: Correct `triggers`, `depends-on`, or `description`

### Trigger (Auto-generate Hooks)

```bash
/skill-kit trigger compile     # Scan skills -> generate dispatcher -> register in settings.json
/skill-kit trigger list        # List registered triggers
/skill-kit trigger dry-run     # Preview only
```

Declare `triggers` in SKILL.md -> auto-generate hook scripts -> auto-register in settings.json.

[Detailed guide](./trigger.md)

## Success Case

**Scenario (2026-03-09)**:
- Found 3 openclaw-related functions
- Proposed 3 options for merging
- Result: Implementation success, user satisfied

**Key factors**:
1. Identification of 3 functions
2. "Merge?" AskUserQuestion
3. Merging skills using skill-writer (multi-topic)

## Ralph Mode (AskUserQuestion bypass)

If `.ralph/` directory exists, operate in Ralph Mode.

**Workflow Change**:

| Step | User Interaction | Workflow |
| ---- | ---------------- | -------- |
| Step 1: Auto-detect | AskUserQuestion (multiSelect) | Summary info to `.ralph/improvements.md` |
| Step 1.5: Merge logic / Structure | - | improvements.md recording |
| Step 2: Requirements | AskUserQuestion | Trigger/scope recommendation to improvements.md |
| Step 3: Type recommendation | Recommend only | improvements.md recording |
| Step 4: Implementation | Direct action | **PROHIBITED** - Use `[NEEDS_REVIEW]` tag |
| Step 5: Validation | Validation | **Auto validation** (after changes are complete) |

## Self-Improvement

After changes are complete, **Self-improve based on conversation**:

1. Identify failure and workaround patterns
2. If candidates found, run `/skill-kit upgrade skill-kit`