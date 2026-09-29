#!/bin/bash
# Stop hook: reap orphaned jq.exe / cygwin-console-helper.exe on Windows.
#
# Root cause: when Claude Code force-kills a hook/command-timeout parent
# (bash.exe) on Windows, the kill does not cascade to pipe-connected
# grandchildren. A `... | jq ...` invocation's jq then blocks forever on a
# stdin read that will never see EOF, and Git Bash's cygwin-console-helper.exe
# (spawned to bridge console I/O for the same bash.exe) gets orphaned the
# same way. Both are permanently hung (0% CPU) and never self-exit, so they
# accumulate over the life of the machine. This hook sweeps them on every
# Stop event using a safe two-part check: parent PID no longer exists AND
# process name is one of the known leak types (jq, cygwin-console-helper,
# or orphaned node.exe running ccstatusline). Never touches active session procs.
#
# Windows-only. No-op elsewhere.
command -v powershell.exe >/dev/null 2>&1 || exit 0

powershell.exe -NoProfile -NonInteractive -Command '
  $ErrorActionPreference = "SilentlyContinue"
  $procs = Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, Name, CommandLine
  $existing = $procs.ProcessId
  $targets = $procs | Where-Object { 
    (($_.Name -match "^(jq|cygwin-console-helper)\.exe$") -or ($_.Name -eq "node.exe" -and $_.CommandLine -match "ccstatusline")) -and 
    ($existing -notcontains $_.ParentProcessId) 
  }
  if ($targets.Count -gt 0) {
    $logDir = Join-Path $env:USERPROFILE ".claude\logs"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $names = ($targets | ForEach-Object { "$($_.Name):$($_.ProcessId)" }) -join ","
    $line = "{0}`treaped {1} orphan(s): {2}" -f (Get-Date -Format o), $targets.Count, $names
    Add-Content -Path (Join-Path $logDir "reap-orphaned-helper-procs.log") -Value $line
    foreach ($p in $targets) {
      try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
    }
  }
' 2>/dev/null

exit 0
