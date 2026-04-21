#!/usr/bin/env bash
# init_plan.sh — extract plan info from macOS Keychain and ~/.codex/auth.json
# and write it to .env so Docker can pick it up at container start time.
#
# Run this once before `docker compose up`, and again only if your plan changes.
#
# Usage:
#   ./scripts/init_plan.sh            # writes CLAUDE_* vars to .env
#   ./scripts/init_plan.sh --print    # prints vars only, does not modify .env

set -euo pipefail

PRINT_ONLY=false
[[ "${1:-}" == "--print" ]] && PRINT_ONLY=true

ENV_FILE="$(dirname "$0")/../.env"
CLAUDE_SUBSCRIPTION_TYPE=""
CLAUDE_RATE_LIMIT_TIER=""

# ── Claude plan (macOS Keychain) ──────────────────────────────────────────────
if command -v security &>/dev/null; then
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
fi

# ── Report ────────────────────────────────────────────────────────────────────
echo "Claude plan:      ${CLAUDE_SUBSCRIPTION_TYPE:-<not found>}"
echo "Claude tier:      ${CLAUDE_RATE_LIMIT_TIER:-<not found>}"

if [[ -z "$CLAUDE_SUBSCRIPTION_TYPE" ]]; then
  echo ""
  echo "Warning: could not read Claude plan from Keychain."
  echo "You can set CLAUDE_SUBSCRIPTION_TYPE manually in .env (e.g. pro, max, free)."
fi

if $PRINT_ONLY; then
  echo ""
  echo "# Add these to your .env:"
  echo "CLAUDE_SUBSCRIPTION_TYPE=${CLAUDE_SUBSCRIPTION_TYPE}"
  echo "CLAUDE_RATE_LIMIT_TIER=${CLAUDE_RATE_LIMIT_TIER}"
  exit 0
fi

# ── Write/update .env ─────────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  echo "" > "$ENV_FILE"
fi

_upsert() {
  local key="$1" val="$2" file="$3"
  if grep -q "^${key}=" "$file" 2>/dev/null; then
    # Replace existing line (macOS + Linux compatible)
    sed -i.bak "s|^${key}=.*|${key}=${val}|" "$file" && rm -f "${file}.bak"
  else
    echo "${key}=${val}" >> "$file"
  fi
}

_upsert "CLAUDE_SUBSCRIPTION_TYPE" "$CLAUDE_SUBSCRIPTION_TYPE" "$ENV_FILE"
_upsert "CLAUDE_RATE_LIMIT_TIER"   "$CLAUDE_RATE_LIMIT_TIER"   "$ENV_FILE"

echo ""
echo "Written to $ENV_FILE"
