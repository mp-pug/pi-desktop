# Pi Dashboard

Ein schlankes Krypto-Trading-Dashboard für den Raspberry Pi 3B+ mit 7-Zoll-Display (800×480).
Zeigt Echtzeit-Marktdaten, Exchange-Kontostände, Freqtrade-Bot-Status, Strategie-Indikatoren, Markt-Sentiment, Krypto-News und eine KI-gestützte Marktanalyse.

## Features

### Home
- Echtzeit-Uhr (sekundengenau) und Wetter via OpenWeatherMap
- Live-Sparkline-Diagramme mit Coin-Icon und Kursänderung (Coins aus Freqtrade-Whitelist)
- Konfigurierbarer Kerzen-Zeitraum (`chart_interval` in Minuten, z.B. 60 = 1h, 240 = 4h)
- Kauf-/Verkauf-Signale aus Freqtrade als farbige Kartenmarkierung
- **Markt-Indikatoren** (alle 10 Min aktualisiert, freie Public APIs):
  - BTC Dominanz mit Balken + Season-Label (CoinGecko)
  - Funding Rate mit zentriertem +/–-Balken (Binance Futures)
  - Long/Short Ratio mit Split-Balken (Binance Futures)
  - Mempool Fees Low/Mid/Fast in sat/vByte (mempool.space)
  - Top Movers: Top 3 Gewinner & Verlierer des Tages (Binance, alle USDT-Paare)
- **Fear & Greed Index** mit Gauge-Balken (alternative.me)
- Kontostände von Kraken und Bitvavo mit EUR-Wert pro Coin
- Gesamt-Portfolio-Wert mit Änderung (basierend auf chart_interval)

### Strategie
- Strategie-Indikatoren pro Coin mit Ampelsystem (grün/gelb/rot)
- Bedingungen werden per AST-Parser direkt aus dem Python-Code der aktiven Freqtrade-Strategie extrahiert
- Zähler „X von Y Signalen erfüllt" pro Coin
- Warnung bei Abweichung zwischen lokaler Strategie-Datei und aktiver Freqtrade-Strategie
- KI-generierte Strategie-Beschreibung (hash-basierter Cache, nur bei Änderung neu generiert)

### Trades
- Offene und abgeschlossene Trades aus Freqtrade
- Statistik-Kopfzeile: Win-Rate, Gesamt-P&L, Anzahl Trades
- Dauer offener Trades (z.B. „seit 3h 20min")

### News
- RSS-Newsfeed-Karten mit Titel, Zusammenfassung, Datum und Quellen-Badge
- Filterleiste nach Quelle (CoinTelegraph, Decrypt, Bitcoin Magazine, ...)
- Deduplizierung: gleiche Headline aus mehreren Feeds erscheint nur einmal
- Ticker am unteren Rand (30-Sekunden-Rotation)
- Alle 15 Minuten automatisch aktualisiert

### KI-Marktanalyse
- Tägliche KI-generierte Marktübersicht pro Coin (Mammouth AI / Claude)
- Cache überlebt Container-Neustarts (`config/ai_summary_cache.json`)
- Manueller Refresh-Button (↺)
- Konfigurierbarer Refresh-Zeitpunkt (`refresh_hour`)

### Trending Coins
- Meistgesuchte 7 Coins der letzten 24h (CoinGecko)
- Karten mit Coin-Icon, Name, Symbol, Preis (USD), 24h-Änderung und Marktkapitalisierung
- Alle 15 Minuten aktualisiert

### Portfolio-Verlauf
- Stündlich gespeicherter Portfolio-Gesamtwert (`config/portfolio_history.json`)
- SVG-Linienchart mit Zeitraumfilter: 24h / 7T / 30T / Alles
- Statistiken: aktueller Wert, Änderung, Maximum, Minimum

## Voraussetzungen

- Docker >= 24
- Docker Compose >= 2
- Freqtrade-Instanz mit aktivierter REST-API (optional, aber für Strategie-Tab erforderlich)

## Installation

```bash
# 1. Repository klonen
git clone git@github.com:mp-pug/pi-desktop.git
cd pi-desktop

# 2. Konfigurationsdatei anlegen
cp config/config.example.json config/config.json
nano config/config.json

# 3. Strategie-Datei ablegen (optional)
cp /pfad/zur/MeineStrategie.py strategies/

# 4. Container bauen und starten
docker compose up -d --build
```

Das Dashboard ist danach unter `http://<raspberry-ip>` erreichbar.

## Konfiguration

Alle Einstellungen befinden sich in `config/config.json`. Die Datei wird bei Änderung automatisch neu eingelesen (mtime-basiertes Caching) – **kein Neubauen oder Neustart nötig**.

### Felder

| Feld | Pflicht | Beschreibung |
|---|---|---|
| `timezone` | ✓ | Zeitzone, z.B. `Europe/Berlin` |
| `openweather.api_key` | – | API-Key von [openweathermap.org](https://openweathermap.org) |
| `openweather.city` | – | Stadtname für die Wetterabfrage |
| `kraken.api_key` | – | Kraken API-Key (Berechtigung: Query Funds) |
| `kraken.api_secret` | – | Kraken API-Secret |
| `bitvavo.api_key` | – | Bitvavo API-Key (Berechtigung: View) |
| `bitvavo.api_secret` | – | Bitvavo API-Secret |
| `freqtrade.url` | – | URL der Freqtrade REST-API, z.B. `http://192.168.1.2:8080` |
| `freqtrade.username` | – | Freqtrade API-Benutzername |
| `freqtrade.password` | – | Freqtrade API-Passwort |
| `mammouth.api_key` | – | API-Key für Mammouth AI |
| `mammouth.model` | – | Modell-ID, z.B. `claude-sonnet-4-5` |
| `mammouth.url` | – | API-Endpunkt |
| `mammouth.refresh_hour` | – | Stunde für täglichen KI-Refresh (0–23, Default: `6`) |
| `chart_interval` | – | Kerzen-Intervall in Minuten (Default: `60`). Gültige Werte: `1`, `5`, `15`, `30`, `60`, `240`, `1440`, `10080` |
| `rss_feeds` | – | Liste von RSS-Feed-URLs |

> `config/config.json` enthält API-Keys und ist via `.gitignore` vom Repository ausgeschlossen.
> Nur `config/config.example.json` wird eingecheckt.

## Keyboard-Shortcuts

| Taste | Aktion |
|---|---|
| `1` – `7` | Tab wechseln (Home, Strategie, Trades, News, KI, Portfolio, Trends) |
| `R` | Aktiven Tab manuell neu laden |

## Aktualisierungsintervalle

| Daten | Intervall |
|---|---|
| Uhrzeit | sekündlich |
| Bot-Status / Trades | alle 2 Minuten |
| Kurse & Signale | alle 5 Minuten |
| Markt-Indikatoren + Top Movers | alle 10 Minuten |
| Fear & Greed / Newsfeed / Trending Coins | alle 15 Minuten |
| Wetter | alle 30 Minuten |
| Strategie-Indikatoren | alle 30 Minuten |
| Portfolio-Verlauf | alle 30 Minuten (Datenpunkt stündlich) |
| KI-Marktanalyse | täglich (konfigurierbarer Zeitpunkt) |

## Projektstruktur

```
pi-desktop/
├── backend/
│   ├── app.py              # Flask API (alle Endpunkte)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── nginx.conf          # Reverse-Proxy zum Backend
│   ├── Dockerfile
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── dashboard.js
│           └── marked.min.js
├── config/
│   ├── config.json                  # Zentrale Konfiguration (nicht im Git)
│   ├── config.example.json          # Vorlage
│   ├── strategy_desc_cache.json     # KI-Strategie-Cache (automatisch erstellt)
│   ├── ai_summary_cache.json        # KI-Marktanalyse-Cache (automatisch erstellt)
│   └── portfolio_history.json       # Portfolio-Verlauf (automatisch erstellt)
├── strategies/
│   └── MeineStrategie.py   # Freqtrade-Strategie (wird automatisch erkannt)
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Nützliche Befehle

```bash
# Starten
docker compose up -d

# Stoppen
docker compose down

# Neu starten (nach Konfigurationsänderung)
docker compose restart

# Neu bauen (nach Code-Änderungen)
docker compose up -d --build

# Logs anzeigen
docker compose logs -f
docker compose logs -f backend
docker compose logs -f frontend
```
