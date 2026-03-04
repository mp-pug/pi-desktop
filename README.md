# Pi Dashboard

Ein schlankes Krypto-Trading-Dashboard für den Raspberry Pi 3B+ mit 10-Zoll-Display.
Zeigt Wetter, Echtzeit-Uhr, Live-Kursdiagramme, Exchange-Kontostände, Freqtrade-Strategie-Indikatoren, Krypto-News und eine KI-gestützte Marktanalyse.

## Features

### Home
- Echtzeit-Uhr (sekundengenau) und Wetter via OpenWeatherMap
- Live-Sparkline-Diagramme mit Kursänderung (Coins aus Freqtrade-Whitelist oder Fallback-Liste)
- Konfigurierbarer Kerzen-Zeitraum (`chart_interval` in Minuten, z.B. 60 = 1h, 240 = 4h)
- Kauf-/Verkauf-Signale aus Freqtrade als farbige Kartenmarkierung
- Kontostände von Kraken und Bitvavo

### Strategie
- Strategie-Indikatoren pro Coin mit Ampelsystem (grün = Bedingung erfüllt, rot = nicht erfüllt)
- Bedingungen werden direkt aus dem Python-Code der aktiven Freqtrade-Strategie per AST-Parser extrahiert – kein manuelles Konfigurieren
- Automatischer Abgleich: lokale `.py`-Datei im `strategies/`-Ordner wird mit der in Freqtrade aktiven Strategie verglichen; bei Abweichung erscheint eine Warnung
- KI-generierte Strategie-Beschreibung (Mammouth AI); wird nur neu generiert wenn sich die Strategie-Datei geändert hat (Hash-basierter Cache auf dem Config-Volume)
- Aktualisierung alle 30 Minuten

### News
- RSS-Newsfeed-Karten mit Titel, Zusammenfassung und Link
- Konfigurierbarer RSS-Feed-Ticker am unteren Rand (30-Sekunden-Einblendung)

### KI-Marktanalyse
- Tägliche KI-generierte Marktübersicht pro Coin (Mammouth AI / Claude)
- Konfigurierbarer Refresh-Zeitpunkt (`refresh_hour`)
- Markdown-Rendering via marked.js

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

Alle Einstellungen befinden sich in `config/config.json`.
Diese Datei liegt als Bind-Mount im Container und wird bei jedem Request eingelesen.
**Nach einer Änderung reicht ein `docker compose restart` – kein Neubauen nötig.**

### Felder

| Feld | Pflicht | Beschreibung |
|---|---|---|
| `timezone` | ✓ | Zeitzone, z.B. `Europe/Berlin` |
| `openweather.api_key` | ✓ | API-Key von [openweathermap.org](https://openweathermap.org) |
| `openweather.city` | ✓ | Stadtname für die Wetterabfrage |
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
| `chart_interval` | – | Kerzen-Intervall in Minuten für Sparklines (Default: `60`). Gültige Werte: `1`, `5`, `15`, `30`, `60`, `240`, `1440`, `10080` |
| `rss_feeds` | – | Liste von RSS-Feed-URLs |

> `config/config.json` enthält API-Keys und ist via `.gitignore` vom Repository ausgeschlossen.
> Nur `config/config.example.json` wird eingecheckt.

## Strategie-Integration

Der `strategies/`-Ordner wird als Volume in den Container gemountet.
Die Datei muss die Freqtrade-Strategie-Klasse enthalten (z.B. `StrongTrend_Retest_4H.py`).

Das Dashboard:
1. Fragt Freqtrade nach der aktiven Strategie (`/api/v1/show_config`)
2. Sucht im `strategies/`-Ordner nach einer passenden `.py`-Datei (Dateiname oder Klassenname)
3. Parst `populate_entry_trend()` per AST und extrahiert alle Kaufbedingungen
4. Wertet jede Bedingung gegen die letzten Kerzen aus Freqtrade aus (`/api/v1/pair_candles`)
5. Zeigt das Ergebnis als Ampel pro Coin und Bedingung an

Bei Abweichung zwischen lokaler Datei und aktiver Freqtrade-Strategie erscheint ein Warnhinweis im Strategie-Tab.

Die KI-Beschreibung der Strategie wird beim ersten Start generiert und in `/config/strategy_desc_cache.json` gecacht. Eine Neugenerierung erfolgt nur bei geändertem Strategie-Code (SHA256-Vergleich).

## Aktualisierungsintervalle

| Daten | Intervall |
|---|---|
| Uhrzeit | sekündlich |
| Wetter | alle 30 Minuten |
| Kurse & Signale | alle 5 Minuten |
| Kontostände | alle 2 Minuten |
| Strategie-Indikatoren | alle 30 Minuten |
| Newsfeed (Ticker) | alle 15 Minuten |
| KI-Marktanalyse | täglich (konfigurierbarer Zeitpunkt) |

## Projektstruktur

```
pi-desktop/
├── backend/
│   ├── app.py              # Flask API (Wetter, Kurse, Signale, Strategie, News, KI)
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
│           └── marked.min.js   # Markdown-Rendering (lokal gebündelt)
├── config/
│   ├── config.json                 # Zentrale Konfiguration (nicht im Git)
│   ├── config.example.json         # Vorlage
│   └── strategy_desc_cache.json    # KI-Beschreibungs-Cache (wird automatisch erstellt)
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

# Logs eines einzelnen Containers
docker compose logs -f backend
docker compose logs -f frontend
```
