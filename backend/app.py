import os
import json
import hashlib
import hmac
import base64
import time
import urllib.parse
import requests
import feedparser
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/config/config.json")


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


# ── Wetter ────────────────────────────────────────────────────────────────────

@app.route("/api/weather")
def get_weather():
    try:
        cfg = load_config()
        ow = cfg["openweather"]
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={urllib.parse.quote(ow['city'])}"
            f"&appid={ow['api_key']}"
            f"&units=metric"
            f"&lang=de"
        )
        r = requests.get(url, timeout=10)
        data = r.json()
        if r.status_code != 200:
            message = data.get("message", f"HTTP {r.status_code}")
            return jsonify({"error": f"OpenWeather: {message}"}), r.status_code
        return jsonify({
            "city": data["name"],
            "temp": round(data["main"]["temp"], 1),
            "feels_like": round(data["main"]["feels_like"], 1),
            "description": data["weather"][0]["description"].capitalize(),
            "icon": data["weather"][0]["icon"],
            "humidity": data["main"]["humidity"],
            "wind_speed": round(data["wind"]["speed"] * 3.6, 1),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── RSS Newsfeed ──────────────────────────────────────────────────────────────

@app.route("/api/news")
def get_news():
    try:
        cfg = load_config()
        feeds = cfg.get("rss_feeds", [
            "https://cointelegraph.com/rss",
            "https://coindesk.com/arc/outboundfeeds/rss/",
        ])
        headlines = []
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:8]:
                    title = entry.get("title", "").strip()
                    if title:
                        headlines.append(title)
            except Exception:
                continue
        return jsonify(headlines)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Kraken ────────────────────────────────────────────────────────────────────

def kraken_request(api_key, api_secret, endpoint, data=None):
    if data is None:
        data = {}
    url = "https://api.kraken.com"
    nonce = str(int(time.time() * 1000))
    data["nonce"] = nonce
    post_data = urllib.parse.urlencode(data)
    encoded = (nonce + post_data).encode()
    message = endpoint.encode() + hashlib.sha256(encoded).digest()
    secret = base64.b64decode(api_secret)
    signature = hmac.new(secret, message, hashlib.sha512)
    sig_digest = base64.b64encode(signature.digest()).decode()
    headers = {
        "API-Key": api_key,
        "API-Sign": sig_digest,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    r = requests.post(url + endpoint, data=data, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


@app.route("/api/kraken")
def get_kraken():
    try:
        cfg = load_config()
        kraken = cfg.get("kraken", {})
        api_key = kraken.get("api_key", "")
        api_secret = kraken.get("api_secret", "")
        if not api_key or not api_secret:
            return jsonify({"error": "Kraken API nicht konfiguriert"}), 400

        result = kraken_request(api_key, api_secret, "/0/private/Balance")
        if result.get("error"):
            return jsonify({"error": result["error"]}), 500

        balances = {}
        for asset, amount in result.get("result", {}).items():
            val = float(amount)
            if val > 0:
                # Normalisiere Asset-Namen (XXBT -> BTC, XETH -> ETH, etc.)
                clean = asset.lstrip("XZ") if len(asset) == 4 else asset
                if clean == "BTC" or asset == "XXBT":
                    clean = "BTC"
                balances[clean] = round(val, 8)

        return jsonify(balances)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Bitvavo ───────────────────────────────────────────────────────────────────

def bitvavo_request(api_key, api_secret, endpoint, method="GET", body=""):
    url = "https://api.bitvavo.com/v2"
    timestamp = str(int(time.time() * 1000))
    msg = timestamp + method + "/v2" + endpoint + body
    sig = hmac.new(api_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    headers = {
        "Bitvavo-Access-Key": api_key,
        "Bitvavo-Access-Signature": sig,
        "Bitvavo-Access-Timestamp": timestamp,
        "Bitvavo-Access-Window": "10000",
        "Content-Type": "application/json",
    }
    r = requests.get(url + endpoint, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


@app.route("/api/bitvavo")
def get_bitvavo():
    try:
        cfg = load_config()
        bv = cfg.get("bitvavo", {})
        api_key = bv.get("api_key", "")
        api_secret = bv.get("api_secret", "")
        if not api_key or not api_secret:
            return jsonify({"error": "Bitvavo API nicht konfiguriert"}), 400

        result = bitvavo_request(api_key, api_secret, "/balance")
        if isinstance(result, dict) and result.get("errorCode"):
            return jsonify({"error": result.get("error")}), 500

        balances = {}
        for entry in result:
            available = float(entry.get("available", 0))
            in_order = float(entry.get("inOrder", 0))
            total = available + in_order
            if total > 0:
                balances[entry["symbol"]] = round(total, 8)

        return jsonify(balances)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Kursdiagramme (öffentlich, kein API-Key nötig) ───────────────────────────

# Kraken Handelspaar-Mapping
WATCHLIST = {
    "BTC":  "XXBTZEUR",
    "ETH":  "XETHZEUR",
    "BNB":  "BNBEUR",
    "DOT":  "DOTEUR",
    "XRP":  "XXRPZEUR",
    "ADA":  "ADAEUR",
    "LINK": "LINKEUR",
    "SOL":  "SOLEUR",
}

@app.route("/api/charts")
def get_charts():
    """
    Liefert für jeden Coin den aktuellen Preis und die letzten 24
    Stunden-Schlusskurse (1h-OHLC) als Sparkline-Daten.
    Verwendet ausschließlich öffentliche Kraken-Endpunkte.
    """
    result = {}
    for symbol, pair in WATCHLIST.items():
        try:
            # OHLC: interval=60 (1h), letzte 25 Kerzen → 24h Sparkline
            r = requests.get(
                "https://api.kraken.com/0/public/OHLC",
                params={"pair": pair, "interval": 60},
                timeout=10,
            )
            data = r.json()
            if data.get("error"):
                raise ValueError(data["error"])
            ohlc = list(data["result"].values())[0]
            # Jede Kerze: [time, open, high, low, close, vwap, volume, count]
            closes = [float(c[4]) for c in ohlc[-25:]]
            current = closes[-1]
            open_24h = closes[0]
            change_pct = ((current - open_24h) / open_24h * 100) if open_24h else 0
            result[symbol] = {
                "price": current,
                "change_pct": round(change_pct, 2),
                "sparkline": closes,
            }
        except Exception as e:
            result[symbol] = {"error": str(e)}
    return jsonify(result)


# ── Freqtrade Signale ────────────────────────────────────────────────────────

# Mapping: Dashboard-Symbol → Freqtrade Pair-Präfix
FT_SYMBOL_MAP = {
    "BTC":  "BTC",
    "ETH":  "ETH",
    "BNB":  "BNB",
    "DOT":  "DOT",
    "XRP":  "XRP",
    "ADA":  "ADA",
    "LINK": "LINK",
    "SOL":  "SOL",
}

def ft_session(cfg):
    """Gibt eine requests.Session mit JWT-Auth für Freqtrade zurück."""
    ft = cfg.get("freqtrade", {})
    s = requests.Session()
    # Freqtrade erwartet application/x-www-form-urlencoded
    resp = s.post(
        ft["url"] + "/api/v1/token/login",
        data={"username": ft["username"], "password": ft["password"]},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=5,
    )
    if resp.status_code == 401:
        raise ValueError("Freqtrade: Ungültige Zugangsdaten (401)")
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise ValueError("Freqtrade: Kein Token erhalten")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s, ft["url"]

@app.route("/api/signals")
def get_signals():
    """
    Fragt die Freqtrade API nach den aktuellen Kauf/Verkauf-Signalen
    für jeden Coin in der Watchlist.
    Rückgabe pro Symbol: "buy" | "sell" | "neutral" | "error"
    """
    try:
        cfg = load_config()
        if "freqtrade" not in cfg:
            return jsonify({"error": "Freqtrade nicht konfiguriert"}), 400

        session, base_url = ft_session(cfg)

        # Whitelist holen um zu wissen welche Pairs aktiv sind
        wl_resp = session.get(base_url + "/api/v1/whitelist", timeout=5)
        wl_resp.raise_for_status()
        whitelist = wl_resp.json().get("whitelist", [])

        # Offene Trades holen
        trades_resp = session.get(base_url + "/api/v1/status", timeout=5)
        trades_resp.raise_for_status()
        open_trades = {t["pair"] for t in trades_resp.json()}

        signals = {}
        for symbol, ft_base in FT_SYMBOL_MAP.items():
            # Passendes Pair in der Whitelist suchen (z.B. BTC/USDT, BTC/EUR …)
            pair = next((p for p in whitelist if p.startswith(ft_base + "/")), None)
            if not pair:
                signals[symbol] = "neutral"
                continue

            # Analyzed dataframe für das Pair abrufen
            df_resp = session.get(
                base_url + "/api/v1/analyzed_dataframe",
                params={"pair": pair, "timeframe": "5m"},
                timeout=5,
            )
            if df_resp.status_code != 200:
                signals[symbol] = "neutral"
                continue

            df_data = df_resp.json()
            columns = df_data.get("columns", [])
            rows = df_data.get("data", [])

            if not rows or not columns:
                signals[symbol] = "neutral"
                continue

            # Letzte Kerze auswerten
            last = dict(zip(columns, rows[-1]))
            enter_long  = bool(last.get("enter_long",  last.get("buy",  0)))
            enter_short = bool(last.get("enter_short", last.get("sell", 0)))

            if pair in open_trades:
                signals[symbol] = "buy"       # Position offen → grün
            elif enter_long:
                signals[symbol] = "buy"
            elif enter_short:
                signals[symbol] = "sell"
            else:
                signals[symbol] = "neutral"

        return jsonify(signals)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Health ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
