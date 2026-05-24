# Topic Route

Receives a topic description, scans existing skills, and recommends **which skill and which topic to place it under**.

## When to Use

- When unsure "where should this feature go?"
- When you need to decide whether to add a new topic to an existing skill or create a new skill
- Use for "topic routing", "topic placement", "where to put", "topic route"

## Workflow

### 1. Collect Input

Receive the following from the user:

- **Topic description**: What the feature does (e.g., "Helm chart lint")
- **Trigger keywords** (optional): When it should activate (e.g., "helm lint", "chart validation")

### 2. Scan All Existing Skills

```bash
# Collect SKILL.md descriptions from all skills
for dir in ~/.claude/skills/*/; do
  skill_name=$(basename "$dir")
  head -5 "$dir/SKILL.md" 2>/dev/null
done

# Check project skills as well
for dir in .claude/skills/*/; do
  skill_name=$(basename "$dir")
  head -5 "$dir/SKILL.md" 2>/dev/null
done

# Check plugin skills as well
for dir in ~/.claude/plugins/*/skills/*/; do
  skill_name=$(basename "$dir")
  head -5 "$dir/SKILL.md" 2>/dev/null
done
```

### 3. Matching Criteria

Select candidates based on the following criteria:

| Criteria | Weight | Description |
|----------|--------|-------------|
| Domain match | High | Same tool/area (e.g., helm, k3s, git) |
| Relevance to existing topics | High | Whether it forms a logical group with existing topics |
| Description keyword similarity | Medium | Whether trigger keywords overlap |
| Topic count limit | Low | Consider splitting if a skill has 10+ topics |

### 4. Verdict Types

#### A. Add Topic to Existing Skill

The most ideal case. Matches the domain of an existing skill.

```
Recommendation: Add "lint" topic to helm-makefile-standard skill
Reason: Helm-related features already exist, and lint belongs to the same build tool area as makefile
```

#### B. Merge into Existing Topic (Add Section)

When it's not large enough to warrant a separate topic.

```
Recommendation: Add "network diagnostics" section to the health topic of k3s skill
Reason: Too small to separate as an independent topic; it's part of health checks
```

#### C. Create New Skill

When it doesn't fit anywhere in existing skills. **Before creating, check slug availability via Skill tool (3rd recurrence — HARD STOP):**

```
Skill("clawhub", "slug <slug-name>")
```

| # | Don't | Do |
|---|-------|-----|
| 1 | Check slug occupancy via `npx skills search` | Call `Skill("clawhub", "slug <name>")` |
| 2 | Run `curl -sI clawhub.ai/skills/<name>` directly | Call `Skill("clawhub", "slug <name>")` |
| 3 | Read slug.md and run curl commands manually | Call `Skill("clawhub", "slug <name>")` |
| 4 | Assume "no slug-occupancy concept" | clawhub.ai uses slug occupancy (307 = occupied, 200 = available) |

```
Recommendation: Create new skill "docker-compose"
Reason: no existing docker-related skill; /clawhub slug "docker-compose" = available
```

### 5. Present Results via AskUserQuestion

```
AskUserQuestion {
  question: "Here's the placement recommendation for topic '{topic_name}'. Where should it go?",
  options: [
    { label: "Add topic to {skillA}", description: "Domain match, N existing topics" },
    { label: "Add as section in {topicB} of {skillB}", description: "Similar feature already exists" },
    { label: "Create new skill", description: "Doesn't fit existing skills" }
  ]
}
```

### 6. Follow-up Action Chaining (HARD STOP — Skill tool call required)

Automatically chain based on selection. **Always call via `Skill("skill-kit", "upgrade/writer ...")` tool** — directly editing SKILL.md with Edit/Write bypasses upgrade/writer's verification procedures (version bump AskUserQuestion, etc.).

| Selection | Chained Action |
|-----------|----------------|
| Add topic to existing skill | `Skill("skill-kit", "upgrade <skill-name> - <topic description>")` |
| Add section to existing topic | Direct Edit (modify within topic file only) |
| Create new skill | `Skill("skill-kit", "writer")` |

| # | Don't | Do |
|---|-------|-----|
| 1 | Write/Edit SKILL.md + topic files directly after route result | Call `Skill("skill-kit", "upgrade ...")` → upgrade procedure verifies version bump |
| 2 | "I know the upgrade procedure, just do it manually" thinking | Skill tool call enforces procedure compliance. Manual = bypass |

## Example

### Input

> "A topic for automatically handling syncthing conflict files"

### Scan Results

```
- sync skill: has syncthing topic (chezmoi + syncthing synchronization)
- syncthing-conflict skill: dedicated skill already exists!
- chezmoi skill: dotfile related
```

### Verdict

```
A syncthing-conflict skill already exists.
→ Add the new feature as a topic to that skill, or enhance the existing SKILL.md.
```

## Notes

- Consider the 1024-character description limit; recommend splitting skills with too many topics
- Also suggest placing in agents (`.claude/agents/`) when more appropriate
  - Complex multi-step tasks → Agent
  - Simple guides/procedures → Skill topic
- If there's overlap with plugin skills, suggest the `dedup` topic
