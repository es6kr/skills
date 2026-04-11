# Multi-Topic Skill Architecture

Define the directory structure for skills with multiple related topics.

## When to Use

- Creating a new skill with multiple sub-topics
- Merging related skills into one
- Organizing complex skills with separate guides

## Directory Structure

```
~/.claude/skills/{skill-name}/
├── SKILL.md          # Unified frontmatter + topic references
├── {topic1}.md       # First topic content (no frontmatter)
├── {topic2}.md       # Second topic content (no frontmatter)
└── scripts/          # Shell/Python scripts called by topics (optional)
    ├── {script}.sh
    └── {script}.py
```

### File Roles

| File | Purpose |
|------|---------|
| `SKILL.md` | Entry point with frontmatter, overview, and topic index |
| `{topic}.md` | Detailed guide for specific topic (no frontmatter) |
| `scripts/` | Reusable scripts referenced from topic files |

### scripts/ Rules

- **All scripts executed by the skill must be inside `scripts/`** — no external path references
- Scripts must be permanent files (no tmp paths)
- Reference scripts from topic files using relative paths: `bash scripts/run.sh`
- If using scripts outside the skill (`~/Sync/...`, `/usr/local/...`) → copy into `scripts/` first

## SKILL.md Template

```yaml
---
name: {skill-name}
description: {unified description}. {topic1} - {desc1}, {topic2} - {desc2}. "{trigger1}", "{trigger2}" triggers
---

# {Skill Name}

{Common theme description}

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| {topic1} | {description} | [{topic1}.md](./{topic1}.md) |
| {topic2} | {description} | [{topic2}.md](./{topic2}.md) |

## Quick Reference

### {Topic1}

Brief summary of topic1.

See [detailed guide](./{topic1}.md).

### {Topic2}

Brief summary of topic2.

See [detailed guide](./{topic2}.md).
```

## Topic File Template

Topic files contain only content (no frontmatter):

```markdown
# {Topic Title}

{Detailed guide content}

## When to Use

{Specific use cases for this topic}

## Instructions

{Step-by-step guidance}

## Examples

{Concrete usage examples}
```

## Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Skill directory | lowercase, hyphens | `argocd-helm` |
| Topic files | lowercase, hyphens, `.md` | `cleanup.md`, `oci.md` |
| SKILL.md | Uppercase | `SKILL.md` |

## Description Format

For multi-topic skills, use this description pattern (no markdown links to save tokens):

```
{Overall purpose}. {topic1} - {brief desc} [{file}], {topic2} - {brief desc} [{file}]. "{trigger1}", "{trigger2}" triggers
```

Example:
```yaml
description: ArgoCD Helm chart management. cleanup - clean Helm metadata [cleanup.md], oci - add OCI registry charts [oci.md]. "argocd helm", "helm metadata", "OCI helm" triggers
```

## Data Store Pattern

Skills that maintain persistent state use a `data/` directory for JSON/cache files.

### Structure

```
~/.claude/skills/{skill-name}/
├── SKILL.md
├── {topic}.md          # Read/write logic for data files
├── data/               # Persistent state (JSON, cache)
│   └── {name}.json
└── scripts/            # Optional automation scripts
```

### When to Use

- Skill needs to remember state across sessions (e.g., published versions, mappings)
- Data is too dynamic for static .md content but too small for a database
- Multiple topics share the same data source

### Rules

| Rule | Rationale |
|------|-----------|
| `data/` only stores JSON/plain text | Keep parseable, no binaries |
| Topics that modify data must update `data/` in the same step | Prevent stale cache |
| Add `data/` to `.clawhubignore` if publishing | User-specific state should not be distributed |
| Include an `updatedAt` field in JSON | Track freshness |

### Example: clawhub skill

```
clawhub/
├── SKILL.md
├── deploy.md         # Writes to data/published.json after publish
├── status.md         # Reads from data/published.json
├── data/
│   └── published.json  # { "updatedAt": "...", "skills": [...] }
└── scripts/
    └── check-slugs.sh
```

### Integration with Other Topics

When creating/upgrading skills with a data store:
- **writer**: Ask if the skill needs persistent state → create `data/` directory
- **upgrade**: When adding a topic that produces state, add `data/` and a corresponding read topic
- **lint**: Verify `data/*.json` files are valid JSON

## Best Practices

1. **Keep topics focused**: Each topic file should cover one specific capability
2. **Cross-reference**: Link between related topics when relevant
3. **Consistent structure**: Use similar headings across topic files
4. **Index in SKILL.md**: Always maintain the Topics table for discoverability
