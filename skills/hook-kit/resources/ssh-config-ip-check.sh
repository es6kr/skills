#!/bin/bash
# Detect Hosts with missing IP when reading SSH config files
# PostToolUse Read hook

FILE_PATH=$(echo "$CLAUDE_TOOL_INPUT" | jq -r '.file_path // empty')

# Check if this is an .ssh/config or *.ssh_config file
if [[ ! "$FILE_PATH" =~ \.ssh/config$ ]] && [[ ! "$FILE_PATH" =~ \.ssh_config$ ]]; then
  exit 0
fi

# Check if file exists
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# Find Hosts with missing IP
# Detect cases where the IP in HostName is absent from the Host line
MISSING_IPS=""

while IFS= read -r line; do
  # Find Host lines (exclude Host * patterns)
  if [[ "$line" =~ ^Host[[:space:]]+(.+)$ ]]; then
    HOSTS="${BASH_REMATCH[1]}"
    # Skip if only wildcard patterns
    if [[ "$HOSTS" =~ ^\*$ ]] || [[ "$HOSTS" =~ ^[a-zA-Z]+\*$ ]]; then
      CURRENT_HOST=""
      continue
    fi
    CURRENT_HOST="$HOSTS"
    CURRENT_HOSTNAME=""
  fi

  # Find HostName lines
  if [[ -n "$CURRENT_HOST" ]] && [[ "$line" =~ ^[[:space:]]*HostName[[:space:]]+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
    IP="${BASH_REMATCH[1]}"
    # Flag if the Host line does not include the IP
    if [[ ! "$CURRENT_HOST" =~ $IP ]]; then
      # Extract first Host name only
      FIRST_HOST=$(echo "$CURRENT_HOST" | awk '{print $1}')
      MISSING_IPS="$MISSING_IPS\n  - Host $FIRST_HOST: $IP missing"
    fi
    CURRENT_HOST=""
  fi
done < "$FILE_PATH"

if [[ -n "$MISSING_IPS" ]]; then
  echo "[ssh-config] Hosts with missing IP found:$MISSING_IPS"
  echo "Adding the IP to Host allows using \`ssh $IP\` with the same config"
fi
