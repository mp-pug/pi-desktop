import os
import re
import ast
import json
import hashlib
import hmac
import base64
import time
import datetime
import threading
import logging
import urllib.parse
import requests
import feedparser
from flask import Flask, jsonify
from flask_cors import CORS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/config/config.json")

REQUIRED_CONFIG_KEYS = [
    ("openweather", "api_key"),
    ("openweather", "city"),
]
OPTIONAL_CONFIG_SECTIONS = ["kraken", "bitvavo", "freqtrade", "mammouth"]


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def validate_config(cfg):
    """Prüft die Konfiguration auf Pflichtfelder und warnt bei fehlenden optionalen Sektionen."""
    errors = []
    for section, key in REQUIRED_CONFIG_KEYS:
        if not cfg.get(section, {}).get(key):
            errors.append(f"'{section}.{key}' fehlt oder ist leer")
    if errors:
        for err in errors:
            logger.error("Config-Fehler: %s", err)
        raise RuntimeError(f"Ungültige Konfiguration: {'; '.join(errors)}")
    for section in OPTIONAL_CONFIG_SECTIONS:
        if section not in cfg:
            logger.warning("Config: Optionale Sektion '%s' nicht konfiguriert", section)


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
            logger.warning("OpenWeather-Fehler: %s", message)
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
        logger.exception("Fehler in get_weather")
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
                logger.warning("RSS-Feed-Fehler für %s", feed_url)
                continue
        logger.info("News geladen: %d Headlines", len(headlines))
        return jsonify(headlines)
    except Exception as e:
        logger.exception("Fehler in get_news")
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
            logger.warning("Kraken API-Fehler: %s", result["error"])
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

        logger.info("Kraken-Balances geladen: %d Assets", len(balances))
        return jsonify(balances)
    except Exception as e:
        logger.exception("Fehler in get_kraken")
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
            logger.warning("Bitvavo API-Fehler: %s", result.get("error"))
            return jsonify({"error": result.get("error")}), 500

        balances = {}
        for entry in result:
            available = float(entry.get("available", 0))
            in_order = float(entry.get("inOrder", 0))
            total = available + in_order
            if total > 0:
                balances[entry["symbol"]] = round(total, 8)

        logger.info("Bitvavo-Balances geladen: %d Assets", len(balances))
        return jsonify(balances)
    except Exception as e:
        logger.exception("Fehler in get_bitvavo")
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

def ft_show_config(session, base_url):
    """Gibt die show_config-Antwort von Freqtrade zurück."""
    resp = session.get(base_url + "/api/v1/show_config", timeout=5)
    resp.raise_for_status()
    return resp.json()

def ft_timeframe(session, base_url):
    """Gibt den konfigurierten Timeframe des Bots zurück."""
    return ft_show_config(session, base_url).get("timeframe", "1h")

def ft_strategy_name(session, base_url):
    """Gibt den Namen der aktiven Freqtrade-Strategie zurück."""
    return ft_show_config(session, base_url).get("strategy")

@app.route("/api/whitelist")
def get_whitelist():
    """Gibt die aktiven Coins des Freqtrade-Bots zurück."""
    try:
        cfg = load_config()
        if "freqtrade" not in cfg:
            return jsonify({"error": "Freqtrade nicht konfiguriert"}), 400
        session, base_url = ft_session(cfg)
        symbols = ft_whitelist_symbols(session, base_url)
        logger.info("Freqtrade-Whitelist geladen: %s", symbols)
        return jsonify(symbols)
    except Exception as e:
        logger.exception("Fehler in get_whitelist")
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
                logger.warning("Freqtrade-Whitelist nicht erreichbar, nutze Fallback")
        # Fallback auf statische Liste
        if not symbols:
            symbols = list(KRAKEN_PAIR_MAP.keys())

        result = {}
        for symbol in symbols:
            kraken_pair = KRAKEN_PAIR_MAP.get(symbol)
            if not kraken_pair:
                logger.debug("Kein Kraken-Pair für Symbol '%s', wird übersprungen", symbol)
                continue
            try:
                r = requests.get(
                    "https://api.kraken.com/0/public/OHLC",
                    params={"pair": kraken_pair, "interval": cfg.get("chart_interval", 60)},
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
                logger.warning("Chart-Fehler für %s: %s", symbol, e)
                result[symbol] = {"error": str(e)}
        logger.info("Charts geladen: %d Coins", len(result))
        return jsonify(result)
    except Exception as e:
        logger.exception("Fehler in get_charts")
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
        logger.error("Freqtrade: Ungültige Zugangsdaten (401)")
        raise ValueError("Freqtrade: Ungültige Zugangsdaten (401)")
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise ValueError("Freqtrade: Kein Token erhalten")
    s.headers.update({"Authorization": f"Bearer {token}"})
    logger.debug("Freqtrade-Session erfolgreich aufgebaut")
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
        timeframe = ft_timeframe(session, base_url)
        for symbol in ft_whitelist_symbols(session, base_url):
            pair = next((p for p in whitelist if p.startswith(symbol + "/")), None)
            if not pair:
                signals[symbol] = "neutral"
                continue

            # Aktuelle Kerzen inkl. Indikatoren abrufen
            df_resp = session.get(
                base_url + "/api/v1/pair_candles",
                params={"pair": pair, "timeframe": timeframe, "limit": 3},
                timeout=5,
            )
            if df_resp.status_code != 200:
                logger.warning("pair_candles für %s nicht verfügbar (HTTP %d)", pair, df_resp.status_code)
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

        logger.info("Signale geladen: %s", signals)
        return jsonify(signals)

    except Exception as e:
        logger.exception("Fehler in get_signals")
        return jsonify({"error": str(e)}), 500


# ── Strategie-Bedingungsparser (AST) ─────────────────────────────────────────

def _col_name(node):
    """Extrahiert den Spaltennamen aus einem dataframe['col']-Knoten."""
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
        return node.slice.value
    return None


def _eval_node(node, rows, local_vars, shift=0):
    """
    Wertet einen AST-Knoten gegen die Datenzeilen aus.
    rows: Liste von Row-Dicts (älteste zuerst), rows[-1] = aktuelle Kerze.
    shift: wie viele Kerzen zurück (0 = aktuell, 1 = vorherige).
    Rückgabe: (wert, erfüllt: True | False | None)
    """
    try:
        row = rows[-(1 + shift)]
    except IndexError:
        return None, None

    # ── Vergleich (col > col, col > 22, …) ──────────────────────────────────
    if isinstance(node, ast.Compare):
        left_val, _ = _eval_node(node.left, rows, local_vars, shift)
        if left_val is None:
            return None, None
        for op, comp in zip(node.ops, node.comparators):
            right_val, _ = _eval_node(comp, rows, local_vars, shift)
            if right_val is None:
                return None, None
            try:
                lf, rf = float(left_val), float(right_val)
            except (TypeError, ValueError):
                return None, None
            if   isinstance(op, ast.Gt):  met = lf > rf
            elif isinstance(op, ast.Lt):  met = lf < rf
            elif isinstance(op, ast.GtE): met = lf >= rf
            elif isinstance(op, ast.LtE): met = lf <= rf
            elif isinstance(op, ast.Eq):  met = lf == rf
            elif isinstance(op, ast.NotEq): met = lf != rf
            else: return None, None
            if not met:
                return False, False
            left_val = right_val
        return True, True

    # ── Pandas-& (BinOp mit BitAnd / BitOr) ─────────────────────────────────
    if isinstance(node, ast.BinOp):
        lv, lm = _eval_node(node.left,  rows, local_vars, shift)
        rv, rm = _eval_node(node.right, rows, local_vars, shift)
        if isinstance(node.op, ast.BitAnd):
            if lm is False or rm is False: return False, False
            if lm is True  and rm is True:  return True, True
            return None, None
        if isinstance(node.op, ast.BitOr):
            if lm is True  or rm is True:   return True, True
            if lm is False and rm is False:  return False, False
            return None, None

    # ── dataframe['col'] → Wert aus der Zeile ────────────────────────────────
    if isinstance(node, ast.Subscript):
        col = _col_name(node)
        if col and col in row:
            try:
                fval = float(row[col])
                return fval, bool(fval)
            except (TypeError, ValueError):
                return row[col], bool(row[col]) if row[col] is not None else (None, None)
        return None, None

    # ── Literal (22, 0.5, …) ─────────────────────────────────────────────────
    if isinstance(node, ast.Constant):
        return node.value, None

    # ── Lokale Variable → auflösen ───────────────────────────────────────────
    if isinstance(node, ast.Name) and node.id in local_vars:
        return _eval_node(local_vars[node.id], rows, local_vars, shift)

    # ── .shift(n) → Auswertung mit erhöhtem Shift ────────────────────────────
    if (isinstance(node, ast.Call) and
            isinstance(node.func, ast.Attribute) and
            node.func.attr == "shift" and
            node.args and isinstance(node.args[0], ast.Constant)):
        n = int(node.args[0].value)
        return _eval_node(node.func.value, rows, local_vars, shift + n)

    # ── Negation ─────────────────────────────────────────────────────────────
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        _, met = _eval_node(node.operand, rows, local_vars, shift)
        return (not met, not met) if met is not None else (None, None)

    return None, None


def _display_value(node, rows, local_vars):
    """Gibt den anzuzeigenden Wert für die linke Seite einer Bedingung zurück."""
    if isinstance(node, ast.Compare):
        val, _ = _eval_node(node.left, rows, local_vars, 0)
        try:
            return round(float(val), 4) if val is not None else None
        except (TypeError, ValueError):
            return val
    # Lokale Variable oder Shift → boolean anzeigen
    _, met = _eval_node(node, rows, local_vars, 0)
    return met


def _condition_label(node, local_vars, shift=0):
    """Erstellt einen lesbaren Label für eine Bedingung."""
    suffix = f" (Kerze -{shift})" if shift > 0 else ""

    # Lokale Variable → Namen verwenden, ggf. mit Shift-Hinweis
    if isinstance(node, ast.Name) and node.id in local_vars:
        return f"{node.id}{suffix}"

    # .shift(n) → rekursiv mit erhöhtem Shift
    if (isinstance(node, ast.Call) and
            isinstance(node.func, ast.Attribute) and
            node.func.attr == "shift" and
            node.args and isinstance(node.args[0], ast.Constant)):
        n = int(node.args[0].value)
        return _condition_label(node.func.value, local_vars, shift + n)

    # Direkte Vergleiche oder Ausdrücke
    try:
        raw = ast.unparse(node)
        cleaned = re.sub(r"dataframe\['([^']+)'\]", r"\1", raw)
        cleaned = re.sub(r'dataframe\["([^"]+)"\]', r"\1", cleaned)
        # .shift(n) im Label lesbar machen
        cleaned = re.sub(r"\.shift\((\d+)\)", r" (Kerze -\1)", cleaned)
        return f"{cleaned}{suffix}"
    except Exception:
        return f"?{suffix}"


def _flatten_bitand(node):
    """Zerlegt (A & B & C) in [A, B, C] (BitAnd-Baum → flache Liste)."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitAnd):
        return _flatten_bitand(node.left) + _flatten_bitand(node.right)
    return [node]


def parse_entry_conditions(code):
    """
    Parst populate_entry_trend() und gibt Liste von
    {'label': str, 'node': ast.AST, 'local_vars': dict} zurück.
    Unterstützt das Muster: dataframe.loc[(A & B & C), 'enter_long'] = 1
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        logger.warning("Strategie-AST-Fehler: %s", e)
        return []

    for fn in ast.walk(tree):
        if not (isinstance(fn, ast.FunctionDef) and fn.name == "populate_entry_trend"):
            continue

        # Lokale Variablenzuweisungen sammeln
        local_vars = {}
        for stmt in fn.body:
            if isinstance(stmt, ast.Assign):
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        local_vars[tgt.id] = stmt.value

        # dataframe.loc[(cond), 'enter_long'] = 1  finden
        for stmt in fn.body:
            if not isinstance(stmt, ast.Assign):
                continue
            tgt = stmt.targets[0] if stmt.targets else None
            if not isinstance(tgt, ast.Subscript):
                continue
            # loc-Slice ist ein Tuple: (condition, 'enter_long')
            sl = tgt.slice
            if isinstance(sl, ast.Index):   # Python < 3.9
                sl = sl.value
            if not isinstance(sl, ast.Tuple) or len(sl.elts) < 2:
                continue
            col_node = sl.elts[-1]
            if not (isinstance(col_node, ast.Constant) and col_node.value == "enter_long"):
                continue

            cond_root = sl.elts[0]
            conditions = _flatten_bitand(cond_root)
            result = []
            for cond in conditions:
                label = _condition_label(cond, local_vars)
                result.append({"label": label, "node": cond, "local_vars": local_vars})
            logger.info("Strategie-Bedingungen geparst: %d Bedingungen", len(result))
            return result

    logger.warning("Kein enter_long-Block in populate_entry_trend gefunden")
    return []

@app.route("/api/strategy")
def get_strategy():
    """
    Gibt pro Coin die Einstiegs-Bedingungen der geladenen Strategie zurück,
    direkt ausgewertet gegen die analysierten Kerzen von Freqtrade.
    Jede Bedingung erhält eine Ampelfarbe: buy (grün) = erfüllt, sell (rot) = nicht erfüllt.
    """
    try:
        cfg = load_config()
        if "freqtrade" not in cfg:
            return jsonify({"error": "Freqtrade nicht konfiguriert"}), 400

        session, base_url = ft_session(cfg)
        ft_config   = ft_show_config(session, base_url)
        timeframe   = ft_config.get("timeframe", "1h")
        ft_strat    = ft_config.get("strategy")
        symbols     = ft_whitelist_symbols(session, base_url)
        whitelist_pairs = session.get(base_url + "/api/v1/whitelist", timeout=5).json().get("whitelist", [])
        open_trades = {t["pair"] for t in session.get(base_url + "/api/v1/status", timeout=5).json()}

        # Lokale Strategie-Datei laden und mit Freqtrade-Strategie abgleichen
        local_fname, strategy_code, mismatch = load_strategy_code(ft_strat)
        entry_conditions = parse_entry_conditions(strategy_code) if strategy_code else []

        strategy_warning = None
        if mismatch:
            local_class = local_fname.replace(".py", "") if local_fname else "—"
            strategy_warning = (
                f"Lokale Strategie '{local_class}' entspricht nicht der "
                f"Freqtrade-Strategie '{ft_strat}'"
            )
            logger.warning("Strategie-Mismatch: lokal='%s', Freqtrade='%s'", local_class, ft_strat)
        elif not entry_conditions:
            logger.warning("Keine Entry-Bedingungen aus Strategie geparst – Fallback auf generische Klassifizierung")

        result = {}
        for symbol in symbols:
            pair = next((p for p in whitelist_pairs if p.startswith(symbol + "/")), None)
            if not pair:
                continue
            try:
                df_resp = session.get(
                    base_url + "/api/v1/pair_candles",
                    params={"pair": pair, "timeframe": timeframe, "limit": 5},
                    timeout=5,
                )
                df_data = df_resp.json()
                columns = df_data.get("columns", [])
                raw_rows = df_data.get("data", [])

                if not raw_rows or not columns:
                    result[symbol] = {"indicators": [], "signal": "neutral", "buy_count": 0, "total": 0}
                    continue

                # Letzte 5 Kerzen als Dicts aufbereiten (für .shift(n)-Auswertung)
                rows = [dict(zip(columns, r)) for r in raw_rows[-5:]]
                last = rows[-1]
                indicators = []
                buy_count = 0

                if entry_conditions:
                    # AST-basierte Auswertung: eine Zeile pro Strategie-Bedingung
                    for cond in entry_conditions:
                        display_val = _display_value(cond["node"], rows, cond["local_vars"])
                        _, met = _eval_node(cond["node"], rows, cond["local_vars"])
                        status = "buy" if met is True else ("sell" if met is False else "neutral")
                        if met is True:
                            buy_count += 1
                        indicators.append({
                            "name":   cond["label"],
                            "value":  display_val,
                            "status": status,
                        })
                else:
                    # Fallback: generische Klassifizierung aller Dataframe-Spalten
                    IGNORED = {
                        "date","open","high","low","close","volume","enter_long","exit_long",
                        "enter_short","exit_short","buy","sell","enter_tag","exit_tag",
                    }
                    for col, val in last.items():
                        if col in IGNORED:
                            continue
                        col_lower = col.lower()
                        try:
                            fval = float(val)
                        except (TypeError, ValueError):
                            continue
                        if fval == 1.0:
                            status = "buy"
                        elif fval == 0.0:
                            status = "neutral"
                        elif "rsi" in col_lower:
                            status = "buy" if fval < 30 else ("sell" if fval > 70 else "neutral")
                        elif "macd" in col_lower and "signal" not in col_lower:
                            status = "buy" if fval > 0 else "sell"
                        else:
                            status = "neutral"
                        indicators.append({"name": col, "value": val, "status": status})
                        if status == "buy":
                            buy_count += 1

                # Gesamtsignal aus Freqtrade-Datensatz
                enter_long = bool(last.get("enter_long", last.get("buy", 0)))
                in_trade = pair in open_trades
                signal = "buy" if (enter_long or in_trade) else "neutral"

                result[symbol] = {
                    "indicators": indicators,
                    "signal":     signal,
                    "buy_count":  buy_count,
                    "total":      len(indicators),
                    "in_trade":   in_trade,
                    "timeframe":  timeframe,
                    "strategy_parsed": bool(entry_conditions),
                }
            except Exception as e:
                logger.warning("Strategie-Fehler für %s: %s", symbol, e)
                result[symbol] = {"error": str(e)}

        if strategy_warning:
            result["_warning"] = strategy_warning
        logger.info("Strategie-Daten geladen: %d Coins, Strategie: %s%s",
                    len(result), ft_strat, " [MISMATCH]" if mismatch else "")
        return jsonify(result)
    except Exception as e:
        logger.exception("Fehler in get_strategy")
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
                    summary = re.sub(r"<[^>]+>", "", summary)[:400]
                    articles.append({
                        "title": title,
                        "summary": summary,
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                    })
            except Exception:
                logger.warning("RSS-Feed-Fehler (full) für %s", feed_url)
                continue
        logger.info("News/full geladen: %d Artikel", len(articles))
        return jsonify(articles)
    except Exception as e:
        logger.exception("Fehler in get_news_full")
        return jsonify({"error": str(e)}), 500


# ── KI-Zusammenfassung (Mammouth AI) ─────────────────────────────────────────

_ai_cache = {"summary": None, "generated_at": 0}
_ai_lock = threading.Lock()

_strategy_info_cache: dict = {"description": None}
_strategy_lock = threading.Lock()

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

    coin_list = ", ".join(coins)
    prompt = (
        f"Erstelle eine strukturierte Marktübersicht auf Deutsch für folgende Kryptowährungen: {coin_list}.\n\n"
        f"Für JEDEN Coin einen eigenen Abschnitt im folgenden Format:\n"
        f"**[SYMBOL]** – [1-2 Sätze zur aktuellen Marktlage, Trend und relevanten Entwicklungen]\n\n"
        f"Danach eine kurze Gesamteinschätzung des Markts (1-2 Sätze).\n"
        f"Nur sachliche Marktübersicht, keine Finanzberatung."
    )

    resp = requests.post(
        api_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 900},
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
        current_hour = datetime.datetime.now().hour

        # Neu generieren wenn: kein Cache, oder Refresh-Stunde erreicht und letzte Gen. > 23h her
        needs_refresh = (
            _ai_cache["summary"] is None or
            (current_hour == refresh_hour and now - _ai_cache["generated_at"] > 23 * 3600)
        )

        if needs_refresh:
            with _ai_lock:
                # Double-checked locking: erneut prüfen nach Lock-Erwerb
                now = time.time()
                still_needs_refresh = (
                    _ai_cache["summary"] is None or
                    (current_hour == refresh_hour and now - _ai_cache["generated_at"] > 23 * 3600)
                )
                if still_needs_refresh:
                    logger.info("Generiere neue KI-Zusammenfassung")
                    _ai_cache["summary"] = generate_ai_summary()
                    _ai_cache["generated_at"] = now
                    logger.info("KI-Zusammenfassung generiert")

        with _ai_lock:
            summary = _ai_cache["summary"]
            generated_at = _ai_cache["generated_at"]

        generated_at_str = datetime.datetime.fromtimestamp(generated_at).strftime("%d.%m.%Y %H:%M") if generated_at else ""
        return jsonify({
            "summary": summary,
            "generated_at": generated_at_str,
        })
    except Exception as e:
        logger.exception("Fehler in get_ai_summary")
        return jsonify({"error": str(e)}), 500


# ── Strategie-Beschreibung ───────────────────────────────────────────────────

STRATEGIES_PATH = os.environ.get("STRATEGIES_PATH", "/strategies")

def load_strategy_code(strategy_name=None):
    """
    Liest die passende .py-Datei aus dem strategies-Verzeichnis.
    Wenn strategy_name angegeben: sucht zuerst nach '{name}.py',
    dann nach einer Datei die 'class {name}' enthält.
    Rückgabe: (fname, code, mismatch: bool)
    mismatch=True bedeutet: gesuchte Strategie nicht gefunden.
    """
    if not os.path.isdir(STRATEGIES_PATH):
        return None, None, False

    files = [f for f in os.listdir(STRATEGIES_PATH) if f.endswith(".py")]
    if not files:
        return None, None, False

    if strategy_name:
        # 1. Dateiname-Match: StrongTrend_Retest_4H.py
        exact = strategy_name + ".py"
        if exact in files:
            fpath = os.path.join(STRATEGIES_PATH, exact)
            with open(fpath, "r") as f:
                return exact, f.read(), False

        # 2. Klassen-Match: suche 'class StrategyName' in allen Dateien
        for fname in files:
            fpath = os.path.join(STRATEGIES_PATH, fname)
            try:
                with open(fpath, "r") as f:
                    code = f.read()
                if f"class {strategy_name}" in code:
                    return fname, code, False
            except OSError:
                continue

        # Kein Match gefunden → Mismatch-Warnung
        logger.warning(
            "Strategie '%s' (Freqtrade) hat kein passendes .py-File im strategies-Ordner", strategy_name
        )
        return files[0], open(os.path.join(STRATEGIES_PATH, files[0])).read(), True

    # Kein Name angegeben → erste Datei nehmen
    fpath = os.path.join(STRATEGIES_PATH, files[0])
    with open(fpath, "r") as f:
        return files[0], f.read(), False

STRATEGY_DESC_CACHE_PATH = os.path.join(os.path.dirname(CONFIG_PATH), "strategy_desc_cache.json")


def _load_desc_cache():
    """Liest den persistenten Beschreibungs-Cache vom Volume."""
    try:
        with open(STRATEGY_DESC_CACHE_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_desc_cache(entry):
    """Schreibt den Beschreibungs-Cache auf das Volume."""
    try:
        with open(STRATEGY_DESC_CACHE_PATH, "w") as f:
            json.dump(entry, f, indent=2)
    except OSError as e:
        logger.warning("Cache-Datei konnte nicht gespeichert werden: %s", e)


def _strategy_hash(code):
    """SHA256-Hash des Strategie-Codes."""
    return hashlib.sha256(code.encode()).hexdigest()


def generate_strategy_description():
    """Lässt die KI den Strategie-Code in verständliche Sprache übersetzen."""
    cfg = load_config()
    ai_cfg = cfg.get("mammouth", {})
    api_key = ai_cfg.get("api_key", "")
    model = ai_cfg.get("model", "claude-sonnet-4-5")
    api_url = ai_cfg.get("url", "https://api.mammouth.ai/v1/chat/completions")

    if not api_key:
        return {"error": "Mammouth API nicht konfiguriert."}

    fname, code, _ = load_strategy_code()
    if not code:
        return {"error": "Keine Strategie-Datei im /strategies Verzeichnis gefunden."}

    prompt = (
        f"Analysiere folgende FreqTrade-Handelsstrategie ({fname}) und erstelle eine "
        f"strukturierte Beschreibung auf Deutsch für einen Trader.\n\n"
        f"Beantworte dabei folgende Punkte:\n"
        f"**Strategie-Überblick** – Name, Zeitrahmen, Handelsstil\n"
        f"**Kaufsignal (Entry)** – Exakte Bedingungen wann ein Kaufsignal ausgelöst wird\n"
        f"**Verkaufssignal (Exit)** – Wann wird eine Position geschlossen (ROI, Stoploss, Signale)\n"
        f"**Indikatoren** – Welche technischen Indikatoren werden verwendet und was bedeuten sie\n"
        f"**Risikomanagement** – Stoploss, Position Sizing, ROI-Ziele\n"
        f"**Stärken & Schwächen** – Kurze Einschätzung\n\n"
        f"Hier ist der Code:\n```python\n{code}\n```"
    )

    resp = requests.post(
        api_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1200},
        timeout=60,
    )
    resp.raise_for_status()
    description = resp.json()["choices"][0]["message"]["content"].strip()
    return {"description": description, "filename": fname, "strategy_hash": _strategy_hash(code)}


@app.route("/api/strategy-info")
def get_strategy_info():
    """Gibt die gecachte KI-Beschreibung der Strategie zurück."""
    with _strategy_lock:
        description = _strategy_info_cache["description"]
    if description is None:
        return jsonify({"error": "Strategie-Beschreibung wird noch generiert, bitte kurz warten."}), 503
    return jsonify(description)


def init_strategy_description():
    """
    Wird beim Start des Containers aufgerufen.
    Generiert die KI-Beschreibung nur neu, wenn sich der Strategie-Code
    seit der letzten Generierung geändert hat (Hash-Vergleich).
    """
    try:
        _, code, _ = load_strategy_code()
        if not code:
            with _strategy_lock:
                _strategy_info_cache["description"] = {
                    "error": "Keine Strategie-Datei im /strategies Verzeichnis gefunden."
                }
            return

        current_hash = _strategy_hash(code)
        cached = _load_desc_cache()

        if cached.get("strategy_hash") == current_hash and cached.get("description"):
            logger.info("Strategie unverändert – nutze gecachte Beschreibung (%s)", cached.get("filename"))
            with _strategy_lock:
                _strategy_info_cache["description"] = {
                    "description": cached["description"],
                    "filename":    cached.get("filename"),
                    "strategy_hash": current_hash,
                }
            return

        logger.info("Strategie geändert oder kein Cache – generiere neue Beschreibung...")
        result = generate_strategy_description()
        with _strategy_lock:
            _strategy_info_cache["description"] = result

        if "error" not in result:
            _save_desc_cache({
                "strategy_hash": current_hash,
                "filename":      result.get("filename"),
                "description":   result["description"],
                "generated_at":  datetime.datetime.now().isoformat(),
            })
            logger.info("Strategie-Beschreibung generiert und gecacht: %s", result.get("filename"))
        else:
            logger.error("Strategie-Beschreibung Fehler: %s", result["error"])

    except Exception as e:
        logger.exception("Strategie-Beschreibung Exception")
        with _strategy_lock:
            _strategy_info_cache["description"] = {"error": str(e)}


# ── Bot-Status ────────────────────────────────────────────────────────────────

@app.route("/api/bot-status")
def get_bot_status():
    """Gibt den aktuellen Status des Freqtrade-Bots zurück."""
    try:
        cfg = load_config()
        if "freqtrade" not in cfg:
            return jsonify({"available": False})

        session, base_url = ft_session(cfg)
        ft_cfg   = ft_show_config(session, base_url)
        count    = session.get(base_url + "/api/v1/count",  timeout=5).json()
        profit_r = session.get(base_url + "/api/v1/profit", timeout=5)
        profit   = profit_r.json() if profit_r.status_code == 200 else {}

        return jsonify({
            "available":     True,
            "state":         ft_cfg.get("state", "unknown"),
            "strategy":      ft_cfg.get("strategy"),
            "open_trades":   count.get("current", 0),
            "max_trades":    count.get("max", 0),
            "profit_closed": round(float(profit.get("profit_closed_coin", 0)), 4),
            "profit_factor": round(float(profit.get("profit_factor",      1)), 2),
        })
    except Exception as e:
        logger.warning("Bot-Status nicht verfügbar: %s", e)
        return jsonify({"available": False, "error": str(e)})


# ── Trade-Historie ─────────────────────────────────────────────────────────────

@app.route("/api/trades")
def get_trades():
    """Gibt offene und abgeschlossene Trades aus Freqtrade zurück."""
    try:
        cfg = load_config()
        if "freqtrade" not in cfg:
            return jsonify({"error": "Freqtrade nicht konfiguriert"}), 400

        session, base_url = ft_session(cfg)

        open_resp   = session.get(base_url + "/api/v1/status",         timeout=5)
        closed_resp = session.get(base_url + "/api/v1/trades",
                                  params={"limit": 30}, timeout=5)

        open_trades   = open_resp.json()   if open_resp.status_code   == 200 else []
        closed_data   = closed_resp.json() if closed_resp.status_code == 200 else {}
        closed_trades = closed_data.get("trades", [])

        # Nur relevante Felder zurückgeben
        def fmt_open(t):
            return {
                "pair":            t.get("pair"),
                "open_rate":       t.get("open_rate"),
                "current_rate":    t.get("current_rate"),
                "profit_pct":      round(float(t.get("current_profit_pct", 0)) * 100, 2),
                "profit_abs":      round(float(t.get("current_profit_abs", 0)), 2),
                "open_date":       t.get("open_date"),
                "stake_amount":    round(float(t.get("stake_amount", 0)), 2),
                "is_open":         True,
            }

        def fmt_closed(t):
            return {
                "pair":        t.get("pair"),
                "open_rate":   t.get("open_rate"),
                "close_rate":  t.get("close_rate"),
                "profit_pct":  round(float(t.get("profit_ratio", 0)) * 100, 2),
                "profit_abs":  round(float(t.get("profit_abs", 0)), 2),
                "open_date":   t.get("open_date"),
                "close_date":  t.get("close_date"),
                "is_open":     False,
            }

        logger.info("Trades geladen: %d offen, %d geschlossen",
                    len(open_trades), len(closed_trades))
        return jsonify({
            "open":   [fmt_open(t)   for t in open_trades],
            "closed": [fmt_closed(t) for t in closed_trades],
        })
    except Exception as e:
        logger.exception("Fehler in get_trades")
        return jsonify({"error": str(e)}), 500


# ── Health ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    try:
        cfg = load_config()
        validate_config(cfg)
        logger.info("Konfiguration erfolgreich geladen und validiert")
    except FileNotFoundError:
        logger.error("Konfigurationsdatei nicht gefunden: %s", CONFIG_PATH)
        raise
    except RuntimeError as e:
        logger.error("Konfigurationsfehler beim Start: %s", e)
        raise

    t = threading.Thread(target=init_strategy_description, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000, debug=False)
