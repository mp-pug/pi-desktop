# Pi Dashboard

Ein schlankes Dashboard für den Raspberry Pi 3B+ mit 10-Zoll-Display.  
Zeigt Wetter, Datum/Uhrzeit, CalDAV-Termine, Krypto-Kontostände (Kraken & Bitvavo) sowie einen RSS-Newsfeed-Ticker.

## Features

- Echtzeit-Uhr (sekundengenau)
- Wetter via OpenWeatherMap API
- Heutige Termine via CalDAV
- Kontostände von Kraken und Bitvavo
- RSS-Newsfeed-Ticker (Krypto-Nachrichten), scrollend am unteren Rand
- Schlichtes dunkles Design
- Optimiert für ARM 32-Bit (linux/arm/v7)

## Voraussetzungen

- Docker >= 24
- Docker Compose >= 2
- Aktiviertes BuildKit (`export DOCKER_BUILDKIT=1`)

## Installation

```bash
# 1. Repository klonen
git clone <repo-url>
cd pi-desktop

# 2. Konfigurationsdatei anpassen
nano config/config.json

# 3. Container bauen und starten
docker compose up -d --build
```

Das Dashboard ist danach unter `http://<raspberry-ip>` erreichbar.

## Konfiguration

Alle Einstellungen befinden sich in `config/config.json`.  
Diese Datei liegt in einem persistenten Docker-Volume und wird beim Start eingelesen.  
**Nach einer Änderung reicht ein `docker compose restart` – kein Neubauen nötig.**

### Felder

| Feld | Beschreibung |
|---|---|
| `timezone` | Zeitzone, z.B. `Europe/Berlin` |
| `openweather.api_key` | API-Key von [openweathermap.org](https://openweathermap.org) |
| `openweather.city` | Stadtname für die Wetterabfrage |
| `caldav.url` | CalDAV-Server-URL |
| `caldav.username` | Benutzername |
| `caldav.password` | Passwort |
| `kraken.api_key` | Kraken API-Key (Berechtigung: Query Funds) |
| `kraken.api_secret` | Kraken API-Secret |
| `bitvavo.api_key` | Bitvavo API-Key (Berechtigung: View) |
| `bitvavo.api_secret` | Bitvavo API-Secret |
| `rss_feeds` | Liste von RSS-Feed-URLs |

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
│   ├── app.py            # Python/Flask API
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── nginx.conf
│   ├── Dockerfile
│   └── static/
│       ├── css/style.css
│       └── js/dashboard.js
├── config/
│   └── config.json       # Zentrale Konfiguration (persistentes Volume)
├── docker-compose.yml
└── README.md
```
