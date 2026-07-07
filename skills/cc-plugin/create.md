# Plugin Creation

Guide for authoring Claude Code plugins.

## Structure

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json          # Required: plugin metadata
├── commands/                 # Slash commands (optional)
│   └── my-command.md
├── agents/                   # Specialized agents (optional)
│   └── my-agent.md
├── skills/                   # Agent Skills (optional)
│   └── my-skill/
│       └── SKILL.md
├── hooks/                    # Event handlers (optional)
├── .mcp.json                 # MCP server config (optional)
└── README.md
```

## plugin.json

```json
{
  "name": "plugin-name",
  "description": "What the plugin does",
  "version": "1.0.0",
  "author": {
    "name": "Author Name",
    "email": "email@example.com"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Lowercase, hyphens only. Must match directory name |
| `description` | string | yes | Plugin functionality description |
| `version` | string | yes | Semver (e.g., "1.0.0") |
| `author.name` | string | no | Author name |
| `author.email` | string | no | Author email |

## Marketplace entry: narrowing components with `strict`

A marketplace.json plugin entry may point `source` at a directory that already
**auto-discovers** components (`commands/`, `agents/`, `skills/`, `hooks/`). This is
common with `source: "./"`, where the repo root is the marketplace root and its
`skills/` directory is auto-discovered.

When such an entry *also* lists explicit component paths (`skills`, `hooks`,
`commands`, `agents`) — typically to expose only a **subset** of what the source root
holds — you MUST set `"strict": true` on the entry. `strict: true` makes the
marketplace entry the **authoritative** component source: the explicit paths take
over and only the listed components load.

With the default `strict: false`, the explicit paths and the auto-discovered
components are treated as two competing manifests → Claude Code rejects the plugin
with a `conflicting manifests` load error (see `troubleshoot.md`).

| # | Don't | Do |
|---|-------|-----|
| 1 | Add `skills`/`hooks` paths to a `source: "./"` entry and leave `strict` unset (defaults to false) | Set `"strict": true` so the entry's component list is authoritative |
| 2 | Resolve the resulting conflict by deleting the entry's component paths | Deleting them re-broadens the plugin to the whole auto-discovered set (e.g., the entire `skills/` collection) — the opposite of the narrowing intent. Use `strict: true` instead |
| 3 | Assume two plugins sharing `source: "./"` can each auto-discover a different subset | Auto-discovery yields the same full set for both. The narrowed plugin must declare explicit paths **and** `strict: true` |

Example — expose only one skill plus its hooks from a multi-skill repo root:

```jsonc
{
  "name": "ralph",
  "source": "./",
  "skills": ["./skills/ralph"],   // narrowed subset
  "hooks": { /* SessionStart / PreToolUse ... */ },
  "strict": true                   // entry is authoritative — required when narrowing on an auto-discovering source
}
```

## Validation Checklist

- [ ] `.claude-plugin/plugin.json` exists
- [ ] `name` matches directory name
- [ ] `version` is valid semver
- [ ] All component files have frontmatter
- [ ] README.md present

## Plugin Locations

| Location | Purpose |
|----------|---------|
| `~/.claude/plugins/my-plugin/` | Personal |
| `.claude/plugins/my-plugin/` | Project-scoped |
