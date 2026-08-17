#!/bin/bash
# check-completed-bloat.sh
# Blocks edits if there are completed items older than the current week.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
if [[ -z "$FILE_PATH" ]]; then
  FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.TargetFile // empty' 2>/dev/null)
fi

if [[ -n "$FILE_PATH" && ( "$FILE_PATH" =~ "fix_plan.md" || "$FILE_PATH" =~ "checklist.md" ) ]]; then
  if [[ -f "$FILE_PATH" ]]; then
    # Interpreter resolution: probe for a WORKING python, not merely a name on
    # PATH. The Windows py3 shim is a Microsoft Store stub that exits 49 without
    # running anything, so a name-only check leaves this validation silently dead.
    PY=""
    for _c in python3 python; do
      if command -v "$_c" >/dev/null 2>&1 && "$_c" -c "pass" >/dev/null 2>&1; then
        PY="$_c"; break
      fi
    done
    if [[ -z "$PY" ]]; then
      echo "WARN: no working python/python3 interpreter found — skipping stale-Completed-entry check" >&2
      exit 0
    fi

    # Run python validation script to check dates of completed items
    # We pass the file path to python
    RESULT=$("$PY" -c "
import sys
import re
import datetime

file_path = sys.argv[1]
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

parts = content.split('## Completed')
if len(parts) < 2:
    sys.exit(0)

completed_section = parts[1]
# Find list items under completed section
items = [line for line in completed_section.splitlines() if line.strip().startswith('-')]

today = datetime.date.today()
# Current week starts on Monday
monday = today - datetime.timedelta(days=today.weekday())
monday_str = monday.strftime('%Y-%m-%d')

date_regex = re.compile(r'\b(20\d{2})-(\d{2})-(\d{2})\b')
stale_items = []

for item in items:
    dates = date_regex.findall(item)
    if dates:
        year, month, day = map(int, dates[0])
        try:
            item_date = datetime.date(year, month, day)
            if item_date < monday:
                stale_items.append((item_date.strftime('%Y-%m-%d'), item.strip()[:60]))
        except ValueError:
            pass

if stale_items:
    print(f'ERROR: Completed section has {len(stale_items)} entries older than the current week (start: {monday_str}).')
    print('Please run the weekly archiving script before editing.')
    for d, text in stale_items[:5]:
        print(f'  - [{d}] {text}...')
    sys.exit(2)
else:
    sys.exit(0)
" "$FILE_PATH" 2>&1)

    RC=$?
    if [[ $RC -ne 0 ]]; then
      echo "$RESULT" >&2
      exit $RC
    fi
  fi
fi
exit 0
