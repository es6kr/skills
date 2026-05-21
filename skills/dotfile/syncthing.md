# Syncthing Integration

Syncs chezmoi source directory via Syncthing to share dotfiles across multiple machines.

## Register Folder via API

Auto-register chezmoi folder using Syncthing REST API:

```bash
# API key (macOS - uses xmllint, grep -oP is GNU-only and doesn't work on macOS)
API_KEY=$(xmllint --xpath '//configuration/gui/apikey/text()' ~/Library/Application\ Support/Syncthing/config.xml)

# Add folder
curl -X POST -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  http://localhost:8384/rest/config/folders \
  -d '{
    "id": ".local/share/chezmoi",
    "label": ".local/share/chezmoi",
    "path": "~/.local/share/chezmoi",
    "type": "sendreceive",
    "versioning": {
      "type": "staggered",
      "params": {"maxAge": "31536000"}
    }
  }'
```

## Auto Ignore Setup

Creates `.stignore` during chezmoi initialization:

```bash
# ~/.local/share/chezmoi/.stignore
.git
(?d).DS_Store
*.bak
```

### `(?d)` Prefix Guide

When a parent directory is deleted on a remote, deletion is blocked if ignored files remain locally:

```
syncing: delete dir: directory has been deleted on a remote device
but contains ignored files (see ignore documentation for (?d) prefix)
```

**`(?d)` prefix**: Allows parent directory deletion even if ignored files exist.

### `(?d)` Application Rules

| Apply | Pattern | Reason |
|-------|---------|--------|
| **Prohibited** | `.bak` | Backup files -- must be preserved locally even on remote deletion |
| **Prohibited** | `.git` | Repository data -- must be preserved locally |
| **Prohibited** | `.env*` | Environment variables/secrets -- must be preserved locally |
| Apply | `.DS_Store` | Volatile metadata |
| Apply | `.ansible`, `.terraform`, `.venv`, `venv`, `node_modules` | Reinstallable runtime/dependencies |
| Apply | `build`, `cache`, `defined`, `dist`, `out`, `target` | Regenerable build artifacts |

### `.claude/.stignore` Current Patterns

```bash
# Backups/secrets -- (?d) prohibited, preserve locally on remote deletion
.bak
.env*
.git
# Regenerable -- (?d) applied, cleaned up together on remote deletion
(?d).ansible
(?d).DS_Store
(?d).terraform
(?d).venv
(?d)build
(?d)cache
(?d)defined
(?d)dist
(?d)node_modules
(?d)out
(?d)target
(?d)venv
# Whitelist
!commands
!hooks
!plugins/marketplaces
!projects
!scripts
*
```

> **Strictly prohibited**: Adding `(?d)` to `.bak`, `.git`, `.env*` -- backup/secret loss on remote deletion

## Directory Structure

```
~/.local/share/chezmoi/
├── .chezmoitemplates/     # Shared data (JSON, etc.)
│   └── mcp-servers.json
├── .chezmoi-lib/          # Shared scripts (executables)
│   ├── executable_*.sh
│   └── ...
├── .stignore              # Syncthing ignore patterns
└── ...
```

## New Machine Setup

```bash
# 1. After syncing chezmoi source via Syncthing
# 2. Initialize chezmoi (keep source directory)
chezmoi init --source ~/.local/share/chezmoi

# 3. Apply
chezmoi apply
```

## Managing Syncthing Default Config with chezmoi

Manage Syncthing defaults via chezmoi modify:

```
~/.local/share/chezmoi/private_Library/private_Application Support/private_Syncthing/
└── modify_private_config.xml.tmpl
```

**Managed items:**
- `defaults/folder`: minDiskFree 1GB, versioning staggered 1 year
- `defaults/ignores`: Global ignore patterns

**Behavior:** On chezmoi apply, settings are applied via Syncthing API -> config.xml auto-updated

## Sync Diagnostics

### Get API Key

**macOS / Linux:**
```bash
API_KEY=$(xmllint --xpath '//configuration/gui/apikey/text()' ~/Library/Application\ Support/Syncthing/config.xml)
```

**Windows (PowerShell):**
```powershell
$configPath = "$env:LOCALAPPDATA\Syncthing\config.xml"
[xml]$xml = Get-Content $configPath
$API_KEY = $xml.configuration.gui.apikey
```

### Check Folder Status

```bash
# Full folder sync status (state, globalFiles, localFiles, needFiles)
curl -s -H "X-API-Key: $API_KEY" "http://localhost:8384/rest/db/status?folder=<FOLDER_ID>"
```

| Field | Meaning |
|-------|---------|
| `state` | `idle` normal, `scanning` scanning, `sync-waiting` waiting to sync |
| `globalFiles` | Total file count across all devices |
| `localFiles` | File count on this device |
| `needFiles` | Files still to be received |

**global > local && needFiles=0**: Files only on other devices (`.stignore` whitelist differences). Normal.

### Check Incomplete Items

```bash
# List of files not yet synced
curl -s -H "X-API-Key: $API_KEY" "http://localhost:8384/rest/db/need?folder=<FOLDER_ID>"

# Completion from a specific device to this device
curl -s -H "X-API-Key: $API_KEY" "http://localhost:8384/rest/db/completion?folder=<FOLDER_ID>&device=<DEVICE_ID>"
```

### Connection Status

```bash
# Check connected/disconnected devices
curl -s -H "X-API-Key: $API_KEY" http://localhost:8384/rest/system/connections

# Check device names
curl -s -H "X-API-Key: $API_KEY" http://localhost:8384/rest/config/devices
```

### Rescan (Index Refresh)

```bash
# Rescan specific folder -- effective for resolving stale states like sync-waiting
curl -s -X POST -H "X-API-Key: $API_KEY" "http://localhost:8384/rest/db/scan?folder=<FOLDER_ID>"
```

### DB Reset (Full Index Reset)

Used when stale entries from offline devices remain or when encountering persistent transfer queue freezes. Settings/keys are preserved; only the index is rebuilt.

> **Note**: `syncthing --reset-database` was removed in v2.0. Replaced by deleting the `index-v2` directory.

**macOS / Linux:**
```bash
# 1. Stop Syncthing
brew services stop syncthing

# 2. Back up and delete index
mv ~/Library/Application\ Support/Syncthing/index-v2 \
   ~/Library/Application\ Support/Syncthing/index-v2.bak

# 3. Restart (index auto-rebuilt)
brew services start syncthing

# 4. Remove backup after verification
rm -rf ~/Library/Application\ Support/Syncthing/index-v2.bak
```

**Windows (PowerShell - Run as Admin if service-managed):**
```powershell
# 1. Stop Syncthing service
Stop-Service syncthing
# Force kill processes if locked
Get-Process | Where-Object { $_.Name -like "*syncthing*" } | Stop-Process -Force

# 2. Back up and delete index
$dbPath = "$env:LOCALAPPDATA\Syncthing\index-v2"
$backupPath = "$env:LOCALAPPDATA\Syncthing\index-v2.bak"
if (Test-Path $backupPath) { Remove-Item $backupPath -Recurse -Force }
Move-Item $dbPath $backupPath -Force

# 3. Start service (index auto-rebuilt)
Start-Service syncthing

# 4. Verify and clean up backup later
Remove-Item $backupPath -Recurse -Force
```

**Check index path**: `syncthing paths` or `syncthing.exe paths` -> "Database location" entry

### Troubleshooting: "Folder Path Missing" on Windows

**Symptom**: Syncthing v2.1.0+ service running under Windows `LocalSystem` account fails to start folder sync with the error:
`Failed initial scan (error="folder path missing" folder.id=<id> ...)`

**Cause**: Syncthing v2.1.0+ service running as `LocalSystem` or in non-interactive sessions cannot expand tilde (`~`) paths (e.g. `~\.claude`) in `config.xml` to a valid user profile directory.

**Solution**:
1. Stop the service.
2. Replace all tilde (`~`) path prefixes in `config.xml` with absolute paths (`C:\Users\<username>\...`).
3. Run the following PowerShell script to automate this conversion:
```powershell
$configPath = "$env:LOCALAPPDATA\Syncthing\config.xml"
[xml]$xml = Get-Content $configPath
$userHome = $env:USERPROFILE
$changed = 0
foreach ($folder in $xml.configuration.folder) {
    $oldPath = $folder.path
    if ($oldPath -match '^~[/\\]') {
        $newPath = $oldPath -replace '^~[/\\]', "$userHome\"
        $newPath = $newPath -replace '/', '\'
        $folder.path = $newPath
        $changed++
    }
}
if ($changed -gt 0) {
    $xml.Save($configPath)
    Write-Host "Paths converted successfully."
}
```
4. Restart the Syncthing service (if using `LocalSystem`, migrate to `shawl` wrapper with `--home` configured for absolute stability).

## Conflict Prevention

- Add temporary file patterns to `.stignore`
- Use chezmoi template conditionals for machine-specific config:

```go
{{ if eq .chezmoi.hostname "macbook" }}
// macbook-specific config
{{ end }}
```
