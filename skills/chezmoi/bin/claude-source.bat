@echo off
chcp 65001 >nul
REM SourceGit Custom Action: 특정 폴더를 추가해서 Claude Code 실행 (Windows)

set "REPO=%~1"

set "GIT_BASH=C:\Program Files\Git\git-bash.exe"

start "" "%GIT_BASH%" --cd="%USERPROFILE%\works\.vscode" -c "claude --add-dir '%REPO%' --dangerously-skip-permissions --resume; exec bash"
