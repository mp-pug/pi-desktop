# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pi-Desktop is a cryptocurrency trading dashboard optimized for Raspberry Pi 3B+ with a 7-inch 800x480 display. It shows real-time market data, exchange balances, Freqtrade bot status, strategy indicators, market sentiment, crypto news, and AI market analysis. The UI is in German.

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
- `backend/` — Flask API (`app.py`, 1300+ lines), all business logic
- `frontend/` — nginx serving static files; reverse-proxies `/api/*` to backend

**Configuration:** `config/config.json` (bind-mounted, not in image). Copy from `config/config.example.json`. Config is reloaded on mtime change (cached, not on every request). All sections are optional — the app degrades gracefully. Secrets: OpenWeather, Kraken, Bitvavo, Freqtrade, Mammouth/Claude API key.

**Strategies:** `strategies/` bind-mounted into the backend container. The backend parses strategy files at runtime.

## Backend (`backend/app.py`)

Key API endpoints:

| Endpoint | Source |
|---|---|
| `/api/weather` | OpenWeatherMap |
| `/api/charts` | Kraken public OHLC API |
| `/api/signals` | Freqtrade REST API |
| `/api/strategy` | AST parser on Freqtrade strategy file |
| `/api/strategy-info` | AI (cached by file hash → `config/strategy_desc_cache.json`) |
| `/api/kraken`, `/api/bitvavo` | Exchange private APIs (HMAC-signed) |
| `/api/news`, `/api/news/full` | RSS feeds (feedparser), deduplicated, with source field |
| `/api/ai-summary` | Daily AI market analysis (in-memory + file cache) |
| `/api/ai-summary/refresh` | POST — clears AI cache for manual regeneration |
| `/api/bot-status`, `/api/trades` | Freqtrade REST API |
| `/api/portfolio-history` | GET — stored portfolio snapshots |
| `/api/portfolio-history/add` | POST — saves portfolio value (throttled to 1/hour) |
| `/health` | Health check |

**Config caching:** `load_config()` checks `os.path.getmtime()` before re-reading the file. Thread-safe via `_config_lock`.

**AST Strategy Parser** (lines ~440–630): Parses `populate_entry_trend()` from Freqtrade Python strategy files. Extracts buy conditions as AST nodes and evaluates them against live candle data. Supports comparisons, pandas bitwise operators (`&`, `|`), `.shift(n)`, local variables, and negation.

**AI Caching:**
- Strategy description: SHA256 hash of the strategy file; persists to `config/strategy_desc_cache.json`
- Daily market analysis: in-memory dict + persisted to `config/ai_summary_cache.json`; loaded on startup; regenerates at configurable hour (`mammouth.refresh_hour`); thread-safe via locks

**Portfolio History:** Stored in `config/portfolio_history.json` as `[[timestamp, value], ...]`. Max 720 entries (30 days × 24h). Frontend POSTs current value after calculating it; backend throttles to 1 entry per hour.

**Exchange Auth:**
- Kraken: nonce-based HMAC-SHA512 (RFC 2104)
- Bitvavo: timestamp-based HMAC-SHA256
- Freqtrade: JWT via HTTP Basic Auth, session cookie reuse

## Frontend (`frontend/`)

Vanilla JS SPA (no framework) to minimize memory on the Pi.

**6 tabs:** Home, Strategie, Trades, News, KI, Portfolio

**Keyboard shortcuts:** `1`–`6` switch tabs, `R` refreshes active tab.

**Polling intervals:**
- Clock: 1s | Bot/Trades: 2 min | Charts+Signals: 5 min (chained) | Indicators: 10 min | Fear&Greed/Ticker/News: 15 min | Weather/Strategy/Portfolio: 30 min | AI: daily

**Home tab layout (top → bottom):**
1. `charts-section` — sparkline cards with coin icon, price, change, buy/sell signal border
2. `indicators-section` — 4 compact market indicator cards (BTC Dominance, Funding Rate, Long/Short, Mempool Fees)
3. `balances-section` — Kraken, Bitvavo, Fear & Greed, Portfolio total

**External APIs called from browser (no key needed):**
- Fear & Greed: `api.alternative.me/fng/`
- BTC Dominance: `api.coingecko.com/api/v3/global`
- Funding Rate: `fapi.binance.com/fapi/v1/fundingRate`
- Long/Short Ratio: `fapi.binance.com/futures/data/globalLongShortAccountRatio`
- Mempool Fees: `mempool.space/api/v1/fees/recommended`
- Coin icons: `assets.coincap.io/assets/icons/{symbol}@2x.png`

**Important patterns:**
- Tabs load data only on first click (lazy loading via `*Loaded` flags)
- `chartsRendering` flag prevents signal updates during chart re-render (race condition guard)
- `loadCharts()` → extracts prices → calls `loadSignals()` (chained, not independent)
- `savePortfolioSnapshot(value)` called from `updatePortfolioTotal()` after computing total; backend throttles writes
- `marked.min.js` renders AI markdown output
- News: deduplicated server-side; filtered client-side by source; `newsActiveFilter` state preserved across refreshes
- Bot-status: flashes `bot-trade-alert` animation when `open_trades` count changes

**Layout:** Fixed 800x480 viewport. Topbar 72px fixed (2 rows). Ticker bar 46px fixed at bottom. Content area: 480 - 72 - 46 - 16px padding - gaps ≈ 332px.

## Platform Notes

- ARM 32-bit (Raspberry Pi 3B+): Docker Compose sets platform hints for multiarch builds
- nginx timeout extended to 120s for AI endpoints
- Viewport locked to `width=800` for the Pi 7" display
