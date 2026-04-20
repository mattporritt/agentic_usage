# Agentic Usage Dashboard

A locally-hosted web dashboard that displays real-time token usage and API stats for [Anthropic (Claude)](https://anthropic.com) and [OpenAI (Codex)](https://openai.com). Designed to run on your local network and display on an iPad in landscape orientation.

## What it does

- Polls the Anthropic and OpenAI admin usage APIs every 60 seconds
- Reads token usage from local JSONL log files written by your own apps
- Displays an always-on dark-theme dashboard with:
  - Per-provider token counts (input / output / total) for today
  - 7-day, 14-day, and 30-day historical token usage charts
  - Live status indicators and graceful "not configured" states when keys are absent

## Why

When running multiple AI-powered tools and agents simultaneously, it is useful to have a single view of token consumption across providers — without logging into multiple billing dashboards. This project aggregates both official API usage data and locally instrumented log files into one place.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  iPad / Browser  →  http://<host>:8000              │
└─────────────────────────────────────────────────────┘
          ↕ polls /api/stats every 60s
┌─────────────────────────────────────────────────────┐
│  FastAPI (Python)          backend/                 │
│  ├── APScheduler polls Anthropic + OpenAI APIs      │
│  ├── Reads ./logs/*.jsonl from Docker volume        │
│  └── Serves compiled React bundle as static files  │
└─────────────────────────────────────────────────────┘
```

**Backend:** Python 3.12 + FastAPI + APScheduler + httpx  
**Frontend:** React + Vite + Tailwind CSS + Recharts  
**Deployment:** Docker (multi-stage build) + docker-compose

---

## Quick start

### 1. Get your API keys

#### Anthropic admin key
Standard Claude API keys **will not work** — you need an admin key with usage read access.

1. Go to [console.anthropic.com](https://console.anthropic.com) → **Settings** → **API Keys**
2. Create a new key with the role **"Billing"** or **"Admin"**
3. Admin keys start with `sk-ant-admin-...`

> **Note:** Usage API access requires an Anthropic organisation account. Individual (personal) accounts do not have access to the usage report API — the Anthropic card will show an error if this applies to you.

#### OpenAI admin key
Standard OpenAI API keys **will not work** — you need an org-level admin key.

1. Go to [platform.openai.com](https://platform.openai.com) → **API keys**
2. Create a key and ensure your account has **Owner** or **Admin** permissions on the organisation
3. Admin keys start with `sk-...` but require org-level access to the usage endpoints

---

### 2. Clone and configure

```bash
git clone git@github.com:mattporritt/agentic_usage.git
cd agentic_usage

cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
ANTHROPIC_ADMIN_KEY=sk-ant-admin-...
OPENAI_ADMIN_KEY=sk-...
LOG_DIR=./logs
POLL_INTERVAL_SECONDS=60
```

Either key can be left blank — that provider will show as "Not configured" on the dashboard.

---

### 3. Run with Docker (recommended)

```bash
docker compose up --build
```

Open `http://localhost:8000` in your browser, or `http://<your-machine-ip>:8000` from your iPad.

To find your machine's local IP:
```bash
# macOS
ipconfig getifaddr en0
```

---

### 4. Run locally (development)

**Backend:**
```bash
pip install -r requirements-dev.txt
uvicorn backend.main:app --reload
```

**Frontend** (in a separate terminal):
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` — the Vite dev server proxies `/api` calls to the FastAPI backend on port 8000, so both must be running.

---

## Local log files

Your own applications can contribute usage data by writing JSONL files to the `logs/` directory (or wherever `LOG_DIR` points).

**Format — one JSON object per line:**
```json
{"timestamp": "2026-04-20T10:30:00Z", "provider": "anthropic", "model": "claude-sonnet-4-6", "input_tokens": 1000, "output_tokens": 500}
{"timestamp": "2026-04-20T10:31:00Z", "provider": "openai", "model": "gpt-4o", "input_tokens": 800, "output_tokens": 300}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `timestamp` | ISO 8601 string | Yes | UTC timestamp of the request |
| `provider` | `"anthropic"` or `"openai"` | Yes | API provider |
| `model` | string | No | Model name (informational only) |
| `input_tokens` | integer | Yes | Input token count |
| `output_tokens` | integer | Yes | Output token count |

Files can use `.json` (array of objects) or `.jsonl` (one object per line) format. Malformed lines are skipped without crashing the parser.

With Docker, point `LOG_DIR` in your `.env` to the directory on your host machine where your apps write logs:

```env
LOG_DIR=/Users/you/my-app/logs
```

The directory is mounted read-only inside the container.

---

## Running tests

```bash
pip install -r requirements-dev.txt
pytest
```

---

## Configuration

All configuration is via environment variables (or `.env` file):

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_ADMIN_KEY` | _(unset)_ | Anthropic admin API key |
| `OPENAI_ADMIN_KEY` | _(unset)_ | OpenAI org-level admin API key |
| `LOG_DIR` | `/app/logs` | Path to local JSONL log files |
| `POLL_INTERVAL_SECONDS` | `60` | How often to poll provider APIs |

---

## Project structure

```
agentic_usage/
├── backend/
│   ├── main.py                  # FastAPI app + lifespan
│   ├── config.py                # Settings via pydantic-settings
│   ├── cache.py                 # In-memory result cache
│   ├── scheduler.py             # APScheduler polling loop
│   ├── log_parser.py            # Local JSONL log reader
│   └── providers/
│       ├── anthropic_client.py  # Anthropic usage API client
│       └── openai_client.py     # OpenAI usage API client
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── hooks/useStats.js    # 60s polling hook
│       └── components/          # Header, ProviderCard, UsageChart
├── tests/                       # pytest test suite
├── logs/                        # Volume mount point for local logs
├── Dockerfile                   # Multi-stage: Node build + Python serve
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt         # Adds pytest, respx
└── .env.example
```
