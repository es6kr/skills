# Cache Cleanup

Clean old plugin cache versions and temporary git directories.

## Usage

```bash
scripts/cache-cleanup.sh [--dry-run] [--verbose]
```

- `--dry-run`: Preview deletions without removing
- `--verbose`: Show detailed output

## What It Cleans

- **Old versions**: Keeps only the latest version per plugin in `~/.claude/plugins/cache/<marketplace>/<plugin>/`
- **Temp git dirs**: Removes `temp_git_*` directories in cache root

## When to Use

- After plugin updates (old versions accumulate)
- When disk space is needed
- Periodically as maintenance
