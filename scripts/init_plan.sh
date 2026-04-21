#!/usr/bin/env bash
# init_plan.sh — extract plan and session info from macOS Keychain
# and write it to .env so Docker can use it at container start time.
#
# Run this once before `docker compose up`, and again only if your plan
# changes (upgrade/downgrade) or your Claude session cookie is reset.
#
# Usage:
#   ./scripts/init_plan.sh            # writes vars to .env
#   ./scripts/init_plan.sh --print    # prints vars only, does not modify .env

set -euo pipefail

PRINT_ONLY=false
[[ "${1:-}" == "--print" ]] && PRINT_ONLY=true

ENV_FILE="$(dirname "$0")/../.env"
CLAUDE_SUBSCRIPTION_TYPE=""
CLAUDE_RATE_LIMIT_TIER=""
CLAUDE_SAFE_STORAGE_KEY=""

if ! command -v security &>/dev/null; then
  echo "Error: 'security' command not found. This script requires macOS."
  exit 1
fi

# ── Claude plan (macOS Keychain: "Claude Code-credentials") ───────────────────
CREDS=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null || true)
if [[ -n "$CREDS" ]]; then
  CLAUDE_SUBSCRIPTION_TYPE=$(python3 -c "
import sys, json
d = json.loads('''$CREDS''')
print(d.get('claudeAiOauth', {}).get('subscriptionType', ''))
" 2>/dev/null || true)
  CLAUDE_RATE_LIMIT_TIER=$(python3 -c "
import sys, json
d = json.loads('''$CREDS''')
print(d.get('claudeAiOauth', {}).get('rateLimitTier', ''))
" 2>/dev/null || true)
fi

# ── Cookie decryption key (macOS Keychain: "Claude Safe Storage") ─────────────
# Used to decrypt the Claude desktop app's Chromium cookie store so the
# container can call the claude.ai rate-limit API using your session.
CLAUDE_SAFE_STORAGE_KEY=$(security find-generic-password \
  -s "Claude Safe Storage" -a "Claude" -w 2>/dev/null || true)

# ── Report ────────────────────────────────────────────────────────────────────
echo "Claude plan:              ${CLAUDE_SUBSCRIPTION_TYPE:-<not found>}"
echo "Claude tier:              ${CLAUDE_RATE_LIMIT_TIER:-<not found>}"
echo "Claude Safe Storage key:  ${CLAUDE_SAFE_STORAGE_KEY:+found}${CLAUDE_SAFE_STORAGE_KEY:-<not found>}"

if [[ -z "$CLAUDE_SUBSCRIPTION_TYPE" ]]; then
  echo ""
  echo "Warning: could not read Claude plan. Set CLAUDE_SUBSCRIPTION_TYPE manually in .env."
fi
if [[ -z "$CLAUDE_SAFE_STORAGE_KEY" ]]; then
  echo ""
  echo "Warning: could not read Claude Safe Storage key."
  echo "Rate-limit usage bars will be unavailable in Docker."
fi

if $PRINT_ONLY; then
  echo ""
  echo "# Add these to your .env:"
  echo "CLAUDE_SUBSCRIPTION_TYPE=${CLAUDE_SUBSCRIPTION_TYPE}"
  echo "CLAUDE_RATE_LIMIT_TIER=${CLAUDE_RATE_LIMIT_TIER}"
  echo "CLAUDE_SAFE_STORAGE_KEY=${CLAUDE_SAFE_STORAGE_KEY}"
  exit 0
fi

# ── Write/update .env ─────────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  echo "" > "$ENV_FILE"
fi

_upsert() {
  local key="$1" val="$2" file="$3"
  if grep -q "^${key}=" "$file" 2>/dev/null; then
    sed -i.bak "s|^${key}=.*|${key}=${val}|" "$file" && rm -f "${file}.bak"
  else
    echo "${key}=${val}" >> "$file"
  fi
}

_upsert "CLAUDE_SUBSCRIPTION_TYPE" "$CLAUDE_SUBSCRIPTION_TYPE" "$ENV_FILE"
_upsert "CLAUDE_RATE_LIMIT_TIER"   "$CLAUDE_RATE_LIMIT_TIER"   "$ENV_FILE"
_upsert "CLAUDE_SAFE_STORAGE_KEY"  "$CLAUDE_SAFE_STORAGE_KEY"  "$ENV_FILE"

echo ""
echo "Written to $ENV_FILE"
