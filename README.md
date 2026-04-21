# Agentic Usage Dashboard

A self-hosted, always-on dashboard that shows real-time token usage and rate-limit status across your AI coding tools — Claude Code and Codex — in a single dark-themed view optimised for an iPad or a secondary monitor.

---

## What it does

When you run multiple AI agents and coding tools simultaneously it is easy to lose track of how much you are consuming, how close you are to rate limits, and what things are costing. This dashboard aggregates all of that into one place without requiring you to log into multiple provider dashboards.

**Per-provider cards show:**
- Tokens consumed today (input, output, cached) with estimated cost
- Cache hit rate and estimated dollar savings from prompt caching
- Rate-limit usage bars for each rolling window (5-hour and 7-day) with burn-rate projection — the bar shows where your usage will be at reset time if you keep going at the current rate
- Plan and subscription tier badge
- Usage credit balance (where available)
- 30-day model breakdown

**Historical chart shows:**
- Output tokens per day for each provider over 7, 14, or 30 days

Data is refreshed automatically every 60 seconds. A manual refresh button is available in the header.

---

## How it works

```
  iPad / Browser
  http://<host-ip>:8000
        │
        │  polls /api/stats every 60 s
        ▼
  ┌─────────────────────────────────────────────────────┐
  │  FastAPI + APScheduler  (Python 3.12)               │
  │                                                     │
  │  Sources polled every 60 s:                         │
  │  ├── ~/.claude/projects/**/*.jsonl  (JSONL logs)    │
  │  ├── ~/.codex/ session files + auth.json            │
  │  ├── claude.ai usage API  (session cookie auth)     │
  │  ├── chatgpt.com rate-limit API  (OAuth token)      │
  │  ├── Anthropic admin usage API  (admin key)         │
  │  └── OpenAI org usage API  (admin key)              │
  │                                                     │
  │  SQLite  →  persists daily totals across restarts   │
  │  Serves compiled React bundle as static files       │
  └─────────────────────────────────────────────────────┘
```

**Backend:** Python 3.12 · FastAPI · APScheduler · httpx · aiosqlite  
**Frontend:** React · Vite · Tailwind CSS · Recharts  
**Deployment:** Docker multi-stage build + Docker Compose

The backend polls data sources on a background schedule and holds results in memory. The frontend polls `/api/stats` and re-renders — no websockets, no build-time config.

---

## Data sources

The dashboard has two tiers of data, and works with whatever subset you configure.

### Local session files (no keys required)

Claude Code writes JSONL session logs to `~/.claude/projects/`. Codex writes session logs to `~/.codex/`. Both directories are volume-mounted read-only into the container. This data is always available if those tools are installed and have been used.

Rate-limit utilisation is read from provider APIs using the OAuth tokens those desktop apps store locally — no admin keys needed for this part.

### Provider usage APIs (admin keys required)

Anthropic and OpenAI both have organisation-level usage APIs that return exact token counts by model. These require admin API keys and are optional — the dashboard degrades gracefully to local session data if they are absent.

### Optional: your own application logs

Any application can contribute usage data by writing JSONL files to the `LOG_DIR` directory. See the [Log file format](#log-file-format) section.

---

## Setup

### Prerequisites

- Docker and Docker Compose installed
- Claude Code and/or Codex installed on the host machine (for local session data)
- macOS (the session-cookie and Keychain integrations are macOS-specific; Linux users get API-key data only)

### 1. Clone the repository

```bash
git clone https://github.com/mattporritt/agentic_usage.git
cd agentic_usage
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in what you have. Everything is optional — the dashboard shows whatever data is available.

```env
# Optional: Anthropic admin key for exact org-level usage data
ANTHROPIC_ADMIN_KEY=sk-ant-admin-...

# Optional: OpenAI org admin key for exact org-level usage data
OPENAI_ADMIN_KEY=sk-...

# Your subscription plan — populated automatically by init_plan.sh (see below)
CLAUDE_SUBSCRIPTION_TYPE=pro
CLAUDE_RATE_LIMIT_TIER=
```

> **Anthropic admin key note:** Standard Claude API keys return 403. You need a key with Billing or Admin role from [console.anthropic.com](https://console.anthropic.com) → Settings → API Keys. Usage API access also requires an organisation account — personal accounts always return 403.

> **OpenAI admin key note:** Standard OpenAI keys return 403. You need an Owner/Admin key from an org account at [platform.openai.com](https://platform.openai.com) → API keys.

### 3. Extract your Claude plan info (macOS only)

Claude Code stores your subscription tier in the macOS Keychain. Run this once to extract it and write it to `.env`:

```bash
./scripts/init_plan.sh
```

This reads `subscriptionType` and `rateLimitTier` from the Keychain entry that Claude Code maintains. You only need to re-run this if your plan changes (e.g. upgrading from Pro to Max).

To preview what will be written without modifying `.env`:

```bash
./scripts/init_plan.sh --print
```

### 4. Start the container

```bash
docker compose up --build
```

On first start the backend fetches all data immediately before serving requests, so the dashboard is populated on first load. Subsequent starts use the SQLite database to backfill history.

Open `http://localhost:8000` in your browser.

---

## Accessing from other devices (iPad, phone, etc.)

The container binds to port 8000 on all interfaces (`0.0.0.0`), so any device on your local network can reach it using your Mac's local IP address.

### Find your Mac's local IP

```bash
ipconfig getifaddr en0        # Wi-Fi
ipconfig getifaddr en1        # Ethernet (if connected)
```

This gives you an address like `192.168.1.42`. Open `http://192.168.1.42:8000` on any device on the same network.

### macOS Firewall

If your Mac's firewall is on it may block incoming connections on port 8000. To allow it:

1. Open **System Settings** → **Network** → **Firewall**
2. Click **Options…**
3. Either toggle off the firewall temporarily, or add a specific rule:  
   - Click **+**, find and add `com.docker.backend` (or `Docker`), set to **Allow incoming connections**

Docker routes traffic through its own network stack — you are allowing Docker's backend process, not an arbitrary open port.

### Make the IP address predictable (recommended)

By default your Mac's local IP can change when you reconnect to Wi-Fi. To keep it stable:

1. Open **System Settings** → **Network** → select your Wi-Fi connection → **Details…**
2. Go to the **TCP/IP** tab
3. Change **Configure IPv4** from **Using DHCP** to **Using DHCP with manual address**
4. Enter a fixed IP in your router's range (e.g. `192.168.1.42`) that is outside the router's DHCP pool

Alternatively, assign a DHCP reservation for your Mac's MAC address in your router's admin panel — the approach varies by router but is usually under LAN Settings or DHCP Reservations.

---

## Local development (without Docker)

Run the backend and frontend separately with hot-reload.

**Backend:**
```bash
pip install -r requirements-dev.txt
uvicorn backend.main:app --reload
```

**Frontend** (separate terminal):
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api` calls to the FastAPI backend on port 8000, so both must be running. Changes to frontend files hot-reload in the browser; backend changes restart uvicorn automatically.

---

## Log file format

Your own applications can contribute token usage by writing to the directory pointed to by `LOG_DIR` (default: `./logs`).

**One JSON object per line:**
```json
{"timestamp": "2026-04-20T10:30:00Z", "provider": "anthropic", "model": "claude-sonnet-4-6", "input_tokens": 1000, "output_tokens": 500}
{"timestamp": "2026-04-20T10:31:00Z", "provider": "openai", "model": "gpt-4o", "input_tokens": 800, "output_tokens": 300}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `timestamp` | ISO 8601 string | Yes | UTC preferred |
| `provider` | `"anthropic"` or `"openai"` | Yes | |
| `model` | string | No | Informational only |
| `input_tokens` | integer | Yes | |
| `output_tokens` | integer | Yes | |

Both `.json` (array of objects) and `.jsonl` (one object per line) are accepted. Malformed lines are skipped.

To point the container at an existing log directory on your host:

```env
# in .env
LOG_DIR=/Users/you/myapp/logs
```

---

## Configuration reference

All settings are read from environment variables or the `.env` file.

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_ADMIN_KEY` | _(unset)_ | Anthropic admin key — enables org usage API |
| `OPENAI_ADMIN_KEY` | _(unset)_ | OpenAI org admin key — enables org usage API |
| `CLAUDE_SUBSCRIPTION_TYPE` | _(unset)_ | Plan badge label (`pro`, `max`, `free`). Set by `init_plan.sh` |
| `CLAUDE_RATE_LIMIT_TIER` | _(unset)_ | Rate limit tier string. Set by `init_plan.sh` |
| `CLAUDE_HOST_DIR` | `~/.claude` | Host path mounted at `/claude` inside the container |
| `CODEX_HOST_DIR` | `~/.codex` | Host path mounted at `/codex` inside the container |
| `DATA_DIR` | `./data` | Host path for SQLite database (persists across restarts) |
| `LOG_DIR` | `./logs` | Host path for optional external JSONL log files |
| `POLL_INTERVAL_SECONDS` | `60` | How often to poll all data sources |

---

## Running tests

```bash
pip install -r requirements-dev.txt
pytest
```

---

## Project structure

```
agentic_usage/
├── backend/
│   ├── main.py              # FastAPI app, lifespan, API endpoints
│   ├── config.py            # Settings (pydantic-settings, reads .env)
│   ├── cache.py             # In-memory result store (module-level dict)
│   ├── scheduler.py         # APScheduler polling loop
│   ├── db.py                # SQLite persistence via aiosqlite
│   ├── log_parser.py        # External JSONL log reader
│   └── sources/
│       ├── claude_code_parser.py  # Parses ~/.claude session JSONL files
│       ├── claude_oauth.py        # Reads plan info from Keychain / env vars
│       ├── claude_usage.py        # claude.ai rate-limit API (session cookie)
│       ├── claude_stats_cache.py  # Reads Claude's own stats-cache JSON
│       ├── codex_parser.py        # Parses ~/.codex session JSONL files
│       ├── codex_oauth.py         # Reads plan info + quota from auth.json JWT
│       └── codex_usage.py         # chatgpt.com rate-limit API (OAuth token)
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── hooks/useStats.js         # 60 s polling hook + manual refresh
│       └── components/
│           ├── Header.jsx            # Title, last-updated, refresh button
│           ├── ProviderCard.jsx      # Per-provider stats card with tooltips
│           └── UsageChart.jsx        # Recharts line chart
├── scripts/
│   └── init_plan.sh         # Extracts Claude plan from Keychain → .env
├── tests/                   # pytest test suite
├── data/                    # SQLite database (git-ignored)
├── logs/                    # Default external log directory (git-ignored)
├── Dockerfile               # Multi-stage: Node build → Python serve
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt     # Adds pytest, respx
└── .env.example
```
