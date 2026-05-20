# Plugin Troubleshooting

Diagnose and fix plugin installation failures, cache sync issues, and HUD errors.

## Common Issues

### "Plugin not installed" / HUD Error

**Cause**: Cache directory missing or incomplete.

**Diagnosis**:

```bash
# Check marketplace exists
ls ~/.claude/plugins/marketplaces/<plugin-name>/

# Check cache exists
ls ~/.claude/plugins/cache/<marketplace>/<plugin-name>/

# Check for built dist (required for HUD plugins)
ls ~/.claude/plugins/cache/<marketplace>/<plugin-name>/<version>/dist/hud/index.js
```

**Fix — Sync marketplace to cache**:

```bash
MARKET=~/.claude/plugins/marketplaces/<plugin-name>
CACHE=~/.claude/plugins/cache/<marketplace>/<plugin-name>/<version>

mkdir -p "$CACHE"

# Copy essential directories
for item in .claude-plugin .mcp.json agents CLAUDE.md dist hooks scripts skills; do
  [ -e "$MARKET/$item" ] && cp -r "$MARKET/$item" "$CACHE/"
done
```

After syncing: **restart Claude Code** (cache loads at session start).

### Plugin recognized but skills/commands not loading

**Cause**: `.claude-plugin/plugin.json` missing from cache.

```bash
cp -r ~/.claude/plugins/marketplaces/<name>/.claude-plugin \
      ~/.claude/plugins/cache/<marketplace>/<name>/<version>/
```

### Plugin HUD load failed — "npm install && npm run build"

**Cause**: `dist/` not built. Plugin has TypeScript source that needs compilation.

```bash
cd ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>
npm install && npm run build
```

### MCP servers not connecting after plugin install

**Cause**: `.mcp.json` not in cache.

```bash
cp ~/.claude/plugins/marketplaces/<name>/.mcp.json \
   ~/.claude/plugins/cache/<marketplace>/<name>/<version>/
```

## Cache Structure Reference

```
~/.claude/plugins/
├── marketplaces/          # Git clones (source of truth)
│   └── <name>/
│       ├── .claude-plugin/plugin.json
│       ├── skills/
│       └── ...
└── cache/                 # Runtime copies (loaded at session start)
    └── <marketplace>/
        └── <plugin>/
            └── <version>/
                ├── .claude-plugin/
                ├── .mcp.json
                ├── agents/
                ├── dist/
                ├── hooks/
                ├── scripts/
                └── skills/
```

## Key Rules

- **Marketplace = source of truth**, cache = runtime copy
- Cache loads at **session start** — changes need restart
- Missing files in cache → copy from marketplace
- `dist/hud/index.js` required for HUD plugins
- `temp_git_*` directories in cache are safe to delete
