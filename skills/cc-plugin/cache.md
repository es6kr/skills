# Cache Cleanup

Clean old plugin cache versions and temporary git directories.

> **⚠️ This topic is cleanup-only.**
> If the user says "cache miss", "cache error", "load error", or any plugin diagnostic phrase — **stop and route to [troubleshoot.md](./troubleshoot.md) instead**. cache.md does not diagnose anything; it only deletes stale versions.

## Usage

```bash
resources/cache-cleanup.sh [--dry-run] [--verbose]
```

- `--dry-run`: Preview deletions without removing
- `--verbose`: Show detailed output

> **Platform**: cross-platform (macOS, Linux, WSL). The script tries BSD-style birthtime
> (`stat -f "%B"`) first, falls back to Linux birthtime (`stat -c "%W"`, often `0` on filesystems
> that don't track it), then falls back again to modification time (`stat -c "%Y"`) so version
> ordering is still correct everywhere. (This note previously said "macOS only" — that was stale;
> the fallback chain is already implemented in `resources/cache-cleanup.sh`.)

## What It Cleans

- **Old versions**: Keeps only the latest version per plugin in `~/.claude/plugins/cache/<marketplace>/<plugin>/`
- **Temp git dirs**: Removes `temp_git_*` directories in cache root

## When to Use

- After plugin updates (old versions accumulate)
- When disk space is needed
- Periodically as maintenance
