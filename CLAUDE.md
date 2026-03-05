# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pi-Desktop is a cryptocurrency trading dashboard optimized for Raspberry Pi 3B+ with a 7-inch 800x480 display. It shows real-time market data, exchange balances, Freqtrade bot status, strategy indicators, crypto news, and AI market analysis. The UI is in German.

## Commands

```bash
# Start all services
docker compose up -d

# Rebuild after code changes
docker compose up -d --build

# Restart after config changes (no rebuild needed)
docker compose restart

# View logs
docker compose logs -f backend
docker compose logs -f frontend

# Stop
docker compose down
```

Dashboard is accessible at `http://<raspberry-ip>` (port 80). Backend API at port 5000.

## Architecture

**Two services via Docker Compose:**
- `backend/` — Flask API (`app.py`, 1100+ lines), all business logic
- `frontend/` — nginx serving static files; reverse-proxies `/api/*` to backend

**Configuration:** `config/config.json` (bind-mounted, not in image). Copy from `config/config.example.json`. Config is reloaded on every request (hot-reload without container restart). Secrets: OpenWeather, Kraken, Bitvavo, Freqtrade, Mammouth/Claude API key.

**Strategies:** `strategies/` bind-mounted into the backend container. The backend parses strategy files at runtime.

## Backend (`backend/app.py`)

Key API endpoints and what drives them:

| Endpoint | Source |
|---|---|
| `/api/charts` | Kraken public OHLC API |
| `/api/signals` | Freqtrade REST API |
| `/api/strategy` | AST parser on Freqtrade strategy file |
| `/api/strategy-info` | AI (cached by file hash) |
| `/api/kraken`, `/api/bitvavo` | Exchange private APIs (HMAC-signed) |
| `/api/news`, `/api/news/full` | RSS feeds (feedparser) |
| `/api/ai-summary` | Daily AI market analysis (in-memory cache) |
| `/api/bot-status`, `/api/trades` | Freqtrade REST API |

**AST Strategy Parser** (lines ~424–617): Parses `populate_entry_trend()` from Freqtrade Python strategy files. Extracts buy conditions as AST nodes and evaluates them against live candle data. Supports comparisons, pandas bitwise operators (`&`, `|`), `.shift(n)`, local variables, and negation.

**AI Caching:**
- Strategy description: SHA256 hash of the strategy file; persists to `config/strategy_desc_cache.json`
- Daily market analysis: in-memory, regenerates at configurable hour (`mammouth.refresh_hour`); thread-safe via locks

**Exchange Auth:**
- Kraken: nonce-based HMAC-SHA512 (RFC 2104)
- Bitvavo: timestamp-based HMAC-SHA256
- Freqtrade: JWT via HTTP Basic Auth, session cookie reuse

## Frontend (`frontend/`)

Vanilla JS SPA (no framework) to minimize memory on the Pi.

**5 tabs:** Home (charts + balances), Strategie (indicators), Trades, News, KI (AI analysis)

**Polling intervals:**
- Clock: 1s | Balances/Bot/Trades: 2 min | Charts+Signals: 5 min (chained) | Ticker: 15 min | Strategy: 30 min | Weather: 30 min

**Important patterns:**
- Tabs load data only on first click (lazy loading)
- `chartsRendering` flag prevents signal updates during chart re-render (race condition guard)
- `loadCharts()` → extracts prices → calls `loadSignals()` (they are chained, not independent)
- `marked.min.js` renders AI markdown output

**Layout:** Fixed 800x480 viewport. Topbar 64px fixed (2 rows). Ticker bar 28px fixed at bottom. Bot-status dot uses `position: fixed` overlay.

## Platform Notes

- ARM 32-bit (Raspberry Pi 3B+): Docker Compose sets platform hints for multiarch builds
- nginx timeout extended to 120s for AI endpoints
- Viewport locked to `width=800` for the Pi 7" display
