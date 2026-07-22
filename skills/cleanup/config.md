# Config (enable/disable tasks)

Enable or disable each task of the cleanup skill individually.

## Config File

`cleanup/.config.json`

### Default (all enabled)

```json
{
  "agentify": true,
  "doc-recommend": true,
  "infra-check": true,
  "memory": true,
  "weekly-report": true
}
```

## Commands

### View current settings

```
/cleanup config
```

Reads the config file and displays the current state.
If the file does not exist, displays the default (all enabled).

### Disable a task

```
/cleanup config disable <task-name>
```

Examples:
```
/cleanup config disable memory        # disable memory storage
/cleanup config disable infra-check   # disable infra check
```

### Enable a task

```
/cleanup config enable <task-name>
```

Example:
```
/cleanup config enable memory         # enable memory storage
```

## Task Identifiers

| Identifier | Task | Default |
|--------|------|--------|
| `agentify` | Detect automation candidates | true |
| `doc-recommend` | Recommend documentation | true |
| `infra-check` | Infra documentation check | true |
| `memory` | Memory storage (auto memory or Serena) | true |
| `retrospect` | Analyze mistakes and record to feedback/failed-attempts | true |
| `weekly-report` | Update Weekly Report | true |

## How It Works

- `run.md` checks `.config.json` first when executing
- If the file does not exist, all tasks are enabled (default)
- Tasks set to `false` are skipped
- No restart needed after changing settings
