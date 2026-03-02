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


# ── Kraken Pair-Mapping (Freqtrade EUR-Pairs → Kraken OHLC-Pairs) ────────────

KRAKEN_PAIR_MAP = {
    "BTC":  "XXBTZEUR",
    "ETH":  "XETHZEUR",
    "BNB":  "BNBEUR",
    "DOT":  "DOTEUR",
    "XRP":  "XXRPZEUR",
    "ADA":  "ADAEUR",
    "LINK": "LINKEUR",
    "SOL":  "SOLEUR",
}

def ft_whitelist_symbols(session, base_url):
    """Gibt Liste von Coin-Symbolen aus der Freqtrade-Whitelist zurück."""
    resp = session.get(base_url + "/api/v1/whitelist", timeout=5)
    resp.raise_for_status()
    pairs = resp.json().get("whitelist", [])
    # "BTC/EUR" → "BTC"
    return [p.split("/")[0] for p in pairs]

def ft_timeframe(session, base_url):
    """Gibt den konfigurierten Timeframe des Bots zurück."""
    resp = session.get(base_url + "/api/v1/show_config", timeout=5)
    resp.raise_for_status()
    return resp.json().get("timeframe", "1h")

@app.route("/api/whitelist")
def get_whitelist():
    """Gibt die aktiven Coins des Freqtrade-Bots zurück."""
    try:
        cfg = load_config()
        if "freqtrade" not in cfg:
            return jsonify({"error": "Freqtrade nicht konfiguriert"}), 400
        session, base_url = ft_session(cfg)
        symbols = ft_whitelist_symbols(session, base_url)
        return jsonify(symbols)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/charts")
def get_charts():
    """
    Liefert für jeden Coin der Freqtrade-Whitelist den aktuellen Preis
    und 24h-Sparkline-Daten via Kraken Public API.
    """
    try:
        cfg = load_config()
        symbols = []
        if "freqtrade" in cfg:
            try:
                session, base_url = ft_session(cfg)
                symbols = ft_whitelist_symbols(session, base_url)
            except Exception:
                pass
        # Fallback auf statische Liste
        if not symbols:
            symbols = list(KRAKEN_PAIR_MAP.keys())

        result = {}
        for symbol in symbols:
            kraken_pair = KRAKEN_PAIR_MAP.get(symbol)
            if not kraken_pair:
                continue
            try:
                r = requests.get(
                    "https://api.kraken.com/0/public/OHLC",
                    params={"pair": kraken_pair, "interval": 60},
                    timeout=10,
                )
                data = r.json()
                if data.get("error"):
                    raise ValueError(data["error"])
                ohlc = list(data["result"].values())[0]
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Freqtrade Signale & Strategie ────────────────────────────────────────────

def ft_session(cfg):
    """Gibt eine requests.Session mit JWT-Auth für Freqtrade zurück."""
    ft = cfg.get("freqtrade", {})
    s = requests.Session()
    # Freqtrade erwartet HTTP Basic Auth beim Token-Login
    resp = s.post(
        ft["url"] + "/api/v1/token/login",
        auth=(ft["username"], ft["password"]),
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
        for symbol in ft_whitelist_symbols(session, base_url):
            pair = next((p for p in whitelist if p.startswith(symbol + "/")), None)
            if not pair:
                signals[symbol] = "neutral"
                continue

            # Analyzed dataframe für das Pair abrufen
            timeframe = ft_timeframe(session, base_url)
            df_resp = session.get(
                base_url + "/api/v1/analyzed_dataframe",
                params={"pair": pair, "timeframe": timeframe},
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


# ── Strategie-Indikatoren ────────────────────────────────────────────────────

# Felder die keine Indikatoren sind und ignoriert werden sollen
IGNORED_COLS = {
    "date","open","high","low","close","volume","enter_long","exit_long",
    "enter_short","exit_short","buy","sell","enter_tag","exit_tag",
    "buy_tag","sell_reason","trade_duration","current_profit",
}

def classify_indicator(col, value):
    """
    Versucht anhand von Spaltenname und Wert zu klassifizieren:
    'buy' (grün), 'sell' (rot) oder 'neutral' (gelb).
    """
    if value is None:
        return "neutral"
    col_lower = col.lower()
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "neutral"

    # Boolesche Signale
    if val == 1.0:
        if any(x in col_lower for x in ["bull", "buy", "long", "up", "green", "above"]):
            return "buy"
        if any(x in col_lower for x in ["bear", "sell", "short", "down", "red", "below"]):
            return "sell"
        return "buy"  # generischer True-Wert → positiv
    if val == 0.0:
        return "neutral"

    # RSI
    if "rsi" in col_lower:
        if val < 30:
            return "buy"
        if val > 70:
            return "sell"
        return "neutral"

    # MACD
    if "macd" in col_lower and "signal" not in col_lower and "hist" not in col_lower:
        return "buy" if val > 0 else "sell"

    return "neutral"

@app.route("/api/strategy")
def get_strategy():
    """
    Gibt pro Coin alle Strategie-Indikatoren der letzten Kerze zurück,
    jeweils mit Ampelklassifizierung (buy/sell/neutral).
    """
    try:
        cfg = load_config()
        if "freqtrade" not in cfg:
            return jsonify({"error": "Freqtrade nicht konfiguriert"}), 400

        session, base_url = ft_session(cfg)
        symbols = ft_whitelist_symbols(session, base_url)
        timeframe = ft_timeframe(session, base_url)
        whitelist_pairs = session.get(base_url + "/api/v1/whitelist", timeout=5).json().get("whitelist", [])
        open_trades = {t["pair"] for t in session.get(base_url + "/api/v1/status", timeout=5).json()}

        result = {}
        for symbol in symbols:
            pair = next((p for p in whitelist_pairs if p.startswith(symbol + "/")), None)
            if not pair:
                continue
            try:
                df_resp = session.get(
                    base_url + "/api/v1/analyzed_dataframe",
                    params={"pair": pair, "timeframe": timeframe},
                    timeout=5,
                )
                df_data = df_resp.json()
                columns = df_data.get("columns", [])
                rows = df_data.get("data", [])

                if not rows or not columns:
                    result[symbol] = {"indicators": [], "signal": "neutral", "buy_count": 0, "total": 0}
                    continue

                last = dict(zip(columns, rows[-1]))
                indicators = []
                buy_count = 0

                for col, val in last.items():
                    if col in IGNORED_COLS:
                        continue
                    status = classify_indicator(col, val)
                    indicators.append({"name": col, "value": val, "status": status})
                    if status == "buy":
                        buy_count += 1

                # Gesamtsignal
                enter_long = bool(last.get("enter_long", last.get("buy", 0)))
                in_trade = pair in open_trades
                signal = "buy" if (enter_long or in_trade) else "neutral"

                result[symbol] = {
                    "indicators": indicators,
                    "signal": signal,
                    "buy_count": buy_count,
                    "total": len(indicators),
                    "in_trade": pair in open_trades,
                    "timeframe": timeframe,
                }
            except Exception as e:
                result[symbol] = {"error": str(e)}

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── RSS Newsfeed (Volltext) ───────────────────────────────────────────────────

@app.route("/api/news/full")
def get_news_full():
    """Gibt Nachrichten mit Titel, Zusammenfassung und Link zurück."""
    try:
        cfg = load_config()
        feeds = cfg.get("rss_feeds", [
            "https://cointelegraph.com/rss",
            "https://coindesk.com/arc/outboundfeeds/rss/",
        ])
        articles = []
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:10]:
                    title = entry.get("title", "").strip()
                    if not title:
                        continue
                    summary = entry.get("summary", entry.get("description", "")).strip()
                    # HTML-Tags entfernen
                    import re
                    summary = re.sub(r"<[^>]+>", "", summary)[:400]
                    articles.append({
                        "title": title,
                        "summary": summary,
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                    })
            except Exception:
                continue
        return jsonify(articles)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── KI-Zusammenfassung (Mammouth AI) ─────────────────────────────────────────

_ai_cache = {"summary": None, "generated_at": 0}

def generate_ai_summary():
    """Generiert eine KI-Zusammenfassung des Kryptomarkts via Mammouth API."""
    cfg = load_config()
    ai_cfg = cfg.get("mammouth", {})
    api_key = ai_cfg.get("api_key", "")
    model = ai_cfg.get("model", "claude-sonnet-4-5")
    api_url = ai_cfg.get("url", "https://api.mammouth.ai/v1/chat/completions")

    if not api_key:
        return "Mammouth API nicht konfiguriert."

    # Coins aus Freqtrade holen
    coins = list(KRAKEN_PAIR_MAP.keys())
    if "freqtrade" in cfg:
        try:
            session, base_url = ft_session(cfg)
            coins = ft_whitelist_symbols(session, base_url)
        except Exception:
            pass

    prompt = (
        f"Erstelle eine prägnante Zusammenfassung (max. 5 Sätze auf Deutsch) "
        f"des aktuellen Kryptomarkts für folgende Coins: {', '.join(coins)}. "
        f"Berücksichtige aktuelle Markttrends, Sentiment und relevante Entwicklungen. "
        f"Keine Finanzberatung, nur sachliche Marktübersicht."
    )

    resp = requests.post(
        api_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 400},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

@app.route("/api/ai-summary")
def get_ai_summary():
    """Gibt die gecachte KI-Zusammenfassung zurück, generiert sie bei Bedarf neu."""
    try:
        cfg = load_config()
        ai_cfg = cfg.get("mammouth", {})
        refresh_hour = ai_cfg.get("refresh_hour", 6)  # Standard: 06:00 Uhr

        now = time.time()
        import datetime
        current_hour = datetime.datetime.now().hour

        # Neu generieren wenn: kein Cache, oder Refresh-Stunde erreicht und letzte Gen. > 23h her
        needs_refresh = (
            _ai_cache["summary"] is None or
            (current_hour == refresh_hour and now - _ai_cache["generated_at"] > 23 * 3600)
        )

        if needs_refresh:
            _ai_cache["summary"] = generate_ai_summary()
            _ai_cache["generated_at"] = now

        import datetime as dt
        generated_at_str = dt.datetime.fromtimestamp(_ai_cache["generated_at"]).strftime("%d.%m.%Y %H:%M") if _ai_cache["generated_at"] else ""
        return jsonify({
            "summary": _ai_cache["summary"],
            "generated_at": generated_at_str,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Health ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
