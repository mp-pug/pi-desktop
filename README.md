# Pi Dashboard

Ein schlankes Dashboard für den Raspberry Pi 3B+ mit 10-Zoll-Display.  
Zeigt Wetter, Datum/Uhrzeit, Live-Kursdiagramme sowie Krypto-Kontostände (Kraken & Bitvavo) und einen RSS-Newsfeed-Ticker.

## Features

- Schwarze Kopfzeile mit Echtzeit-Uhr (sekundengenau) und Wetter
- Wetter via OpenWeatherMap API (max. 48 Anfragen/Tag)
- Live-Sparkline-Diagramme für BTC, ETH, BNB, DOT, XRP, ADA, LINK, SOL (via Kraken Public API)
- Kontostände von Kraken und Bitvavo (alle 2 Minuten aktualisiert)
- RSS-Newsfeed-Ticker am unteren Rand (Krypto-Nachrichten, 30-Sekunden-Einblendung)
- Helles, elegantes Design – Newsfeed-Leiste schwarz mit weißer Schrift
- Optimiert für ARM 32-Bit (linux/arm/v7)

## Voraussetzungen

- Docker >= 24
- Docker Compose >= 2

## Installation

```bash
# 1. Repository klonen
git clone git@github.com:mp-pug/pi-desktop.git
cd pi-desktop

# 2. Konfigurationsdatei anlegen
cp config/config.example.json config/config.json
nano config/config.json

# 3. Container bauen und starten
docker compose up -d --build
```

Das Dashboard ist danach unter `http://<raspberry-ip>` erreichbar.

## Konfiguration

Alle Einstellungen befinden sich in `config/config.json`.  
Diese Datei liegt als Bind-Mount im Container und wird beim Start eingelesen.  
**Nach einer Änderung reicht ein `docker compose restart` – kein Neubauen nötig.**

### Felder

| Feld | Beschreibung |
|---|---|
| `timezone` | Zeitzone, z.B. `Europe/Berlin` |
| `openweather.api_key` | API-Key von [openweathermap.org](https://openweathermap.org) |
| `openweather.city` | Stadtname für die Wetterabfrage |
| `kraken.api_key` | Kraken API-Key (Berechtigung: Query Funds) |
| `kraken.api_secret` | Kraken API-Secret |
| `bitvavo.api_key` | Bitvavo API-Key (Berechtigung: View) |
| `bitvavo.api_secret` | Bitvavo API-Secret |
| `rss_feeds` | Liste von RSS-Feed-URLs |

> `config/config.json` enthält API-Keys und ist via `.gitignore` vom Repository ausgeschlossen.  
> Nur `config/config.example.json` wird eingecheckt.

## Aktualisierungsintervalle

| Daten | Intervall |
|---|---|
| Uhrzeit | sekündlich |
| Wetter | alle 30 Minuten |
| Kurse / Sparklines | alle 5 Minuten |
| Kontostände | alle 2 Minuten |
| Newsfeed | alle 15 Minuten |

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
```

## Projektstruktur

```
pi-desktop/
├── backend/
│   ├── app.py              # Python/Flask API (Wetter, Kurse, Kontostände, News)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── nginx.conf          # Reverse-Proxy zu Backend
│   ├── Dockerfile
│   └── static/
│       ├── css/style.css
│       └── js/dashboard.js
├── config/
│   ├── config.json         # Zentrale Konfiguration (nicht im Git)
│   └── config.example.json # Vorlage
├── docker-compose.yml
├── .gitignore
└── README.md
```
