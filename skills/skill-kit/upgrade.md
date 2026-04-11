# Skill Upgrade

Analyzes an existing skill and **discovers issues to fix** — adds topics, enhances frontmatter, restructures scripts.

## When to Use

- When adding new topics/features to an existing skill
- When adding new trigger keywords to SKILL.md description
- When migrating scripts within a skill to a proper `scripts/` structure
- When improving this skill (skill-manager) itself

## Core: Conversation-based Problem Discovery

The core of upgrade is **identifying skill limitations, missing topics, and structural issues**.

### Problem Discovery Workflow

1. **Read through the entire conversation and detect these signals**:

| Signal | Example |
|--------|---------|
| Skill did not activate | "Why isn't the skill triggering?" |
| Manual corrections after skill execution | Skill runs → immediate Edit/manual fix |
| User used a workaround | Used bash/edit directly instead of the skill |
| Repeated patterns | Same task performed manually 3+ times |
| Mentions of insufficient output | "This should be included too", "It's missing" |

2. **List discovered problems concretely**:
   - Which skill? → What situation? → What output was insufficient?

3. **Derive improvement proposals**:
   - Can it be solved with a new topic/section?
   - Can it be solved by adding trigger keywords to description?
   - Is a new script needed?

### Example: Session Skill Problems Discovered in This Conversation

```
Problem: /session <id> name it → naming feature didn't exist in skill, implemented manually
Fix: Added rename topic + rename-session.sh script
→ Done
```

```
Problem: Used Edit directly without skill-manager when improving skill
Fix: Added skill-usage.md rule + created skill-manager upgrade topic
→ Done
```

## Language Matching

When adding/modifying content in an existing skill, match the language of the existing content:

1. Read the existing `SKILL.md` and 1-2 topic files
2. If content is **English** → write in **English only**
3. If content is **Korean** → write in **Korean** (technical terms in English OK)
4. If mixed → follow the **majority language**

**Do not** write Korean content in an English skill or vice versa.

## Workflow

### 1. Identify Target Skill

```bash
# Search for skill location
ls ~/.claude/skills/
ls .claude/skills/    # project skills
```

### 2. Analyze Current Structure

- Read `SKILL.md`: check current topics list, description, frontmatter
- Read topic files: understand content, check for duplicates
- Check if `scripts/` exists

### 3. Get Approval for Improvement Candidates via AskUserQuestion ⚠️ Required

**Conversation-based problem discovery → must get user approval before execution.**

Like agentify, present discovered problems first and let the user choose which ones to improve.

```
AskUserQuestion {
  question: "Here are improvement candidates discovered from this conversation. Which ones should be applied?",
  multiSelect: true,
  options: [
    { label: "Add rename topic", description: "Session naming feature was missing, implemented manually" },
    { label: "Add description trigger keywords", description: "Skill activation failure case detected" },
    ...discovered problems
  ]
}
```

**Forbidden**: Immediately fixing upon discovery. Must only modify items selected after AskUserQuestion.

### 4. Plan Improvements

| Improvement Type | Task |
|-----------------|------|
| Add new topic | Create topic file → update SKILL.md topics table |
| Improve frontmatter | Add new trigger keywords to description |
| Integrate scripts | Create `scripts/` folder → migrate scripts → document execution in SKILL.md |
| Add Quick Reference | Add usage section to SKILL.md |

### 4. Execute

**Topic addition pattern:**

```markdown
<!-- New topic file: skill-name/new-topic.md -->
# New Topic

[Content]

## Procedure
...
```

**SKILL.md update checklist:**
- [ ] Add new topic name and trigger keywords to `description:` frontmatter
- [ ] Add row to Topics table in alphabetical order
- [ ] Update Quick Reference section
- [ ] Check `depends-on` field (see procedure below)

**safe-delete rule when removing/replacing skills (⚠️ Required):**

When deleting skills under `.claude`, always:

```bash
mkdir -p ~/.claude/.bak
mv ~/.claude/skills/{old-skill} ~/.claude/.bak/
```

**Never**: Add `.bak` suffix in the same directory (`mv skill skill.bak`)
- This causes Claude Code to still load the `.bak` folder as a skill
- Must move to the `~/.claude/.bak/` root folder

### 4-1. Auto-detect depends-on ⚠️ Required

**When running upgrade, detect references to other skills in the target skill's topic files and automatically update the `depends-on` field.**

Detection patterns:

| Pattern | Meaning | Example |
|---------|---------|---------|
| `/skill-name` | Slash command reference | `/safe-delete`, `/skill-manager upgrade` |
| `Skill("name"` | Skill tool invocation | `Skill("safe-delete", ...)` |
| `skill-manager` (in topic files) | Uses skill-manager procedure | `When malfunction discovered, /skill-manager upgrade` |

Procedure:

1. Grep all `.md` files of the target skill for the above patterns
2. Verify that extracted skill names exist in `~/.claude/skills/` or `.claude/skills/`
3. Add only existing skills to the `depends-on` array
4. If `depends-on` already exists, merge (remove duplicates)

```yaml
# Before (no depends-on)
---
name: ralph
description: ...
---

# After (/safe-delete reference detected in PROMPT.md)
---
name: ralph
depends-on: [safe-delete]
description: ...
---
```

**This step is required, not optional.** It is always performed as a default behavior of upgrade.

### 5. Lint Verification

After upgrade, always run lint:

```
/skill-manager lint <skill-name>
```

## Notes

- Topic files have no frontmatter (only exists in SKILL.md)
- Topics table in SKILL.md must always be kept in alphabetical order
- Scripts are created as permanent files in `scripts/` (tmp files forbidden)
