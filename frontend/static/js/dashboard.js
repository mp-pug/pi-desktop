const API = "";

const DAYS   = ["Sonntag","Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag"];
const MONTHS = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"];

// ── Uhr ───────────────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2,"0");
  const m = String(now.getMinutes()).padStart(2,"0");
  const s = String(now.getSeconds()).padStart(2,"0");
  document.getElementById("clock").textContent = `${h}:${m}:${s}`;
  const day = DAYS[now.getDay()];
  document.getElementById("date-display").textContent =
    `${day}, ${now.getDate()}. ${MONTHS[now.getMonth()]} ${now.getFullYear()}`;
}
setInterval(updateClock, 1000);
updateClock();

// ── Tab-Navigation ────────────────────────────────────────────────────────────
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "trades"    && !tradesLoaded)    loadTrades();
    if (btn.dataset.tab === "news"      && !newsLoaded)      loadNewsTab();
    if (btn.dataset.tab === "ai"        && !aiLoaded)        loadAI();
    if (btn.dataset.tab === "portfolio" && !portfolioLoaded) loadPortfolioHistory();
    if (btn.dataset.tab === "trends"    && !trendsLoaded)    loadTrending();
  });
});

// ── Keyboard-Shortcuts ────────────────────────────────────────────────────────
const TAB_KEYS = { "1":"home","2":"trades","3":"news","4":"ai","5":"portfolio","6":"trends" };
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
  if (TAB_KEYS[e.key]) {
    document.querySelector(`.tab-btn[data-tab="${TAB_KEYS[e.key]}"]`)?.click();
    return;
  }
  if (e.key === "r" || e.key === "R") {
    const active = document.querySelector(".tab-btn.active")?.dataset.tab;
    if (active === "home")      { loadCharts().then(() => loadSignals()); loadBalances(); loadFearGreed(); loadMarketIndicators(); }
    if (active === "trades")    { tradesLoaded = false; loadTrades(); }
    if (active === "news")      { newsLoaded = false; loadNewsTab(); }
    if (active === "ai")        { aiLoaded = false; loadAI(); }
    if (active === "portfolio") { loadPortfolioHistory(); }
    if (active === "trends")    { loadTrending(); }
  }
});

// ── Hilfsfunktionen ───────────────────────────────────────────────────────────
async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function formatPrice(n) {
  if (n >= 1000) return n.toLocaleString("de-DE", {maximumFractionDigits: 0});
  if (n >= 1)    return n.toLocaleString("de-DE", {minimumFractionDigits: 2, maximumFractionDigits: 2});
  return n.toLocaleString("de-DE", {minimumFractionDigits: 4, maximumFractionDigits: 6});
}

function formatAmount(n) {
  const v = parseFloat(n);
  if (v >= 1) return v.toLocaleString("de-DE", {minimumFractionDigits: 2, maximumFractionDigits: 6});
  return v.toLocaleString("de-DE", {minimumFractionDigits: 2, maximumFractionDigits: 8});
}

function formatEur(v) {
  if (v >= 1000) return "€\u202f" + v.toLocaleString("de-DE", {minimumFractionDigits: 0, maximumFractionDigits: 0});
  return "€\u202f" + v.toLocaleString("de-DE", {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

function formatDuration(openDateStr) {
  if (!openDateStr) return "";
  const open = new Date(openDateStr.endsWith("Z") ? openDateStr : openDateStr + "Z");
  const diff = Math.floor((Date.now() - open.getTime()) / 1000);
  if (diff < 3600)  return `${Math.floor(diff / 60)}min`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}min`;
  return `${Math.floor(diff / 86400)}T ${Math.floor((diff % 86400) / 3600)}h`;
}

// ── Wetter ────────────────────────────────────────────────────────────────────
async function loadWeather() {
  const el = document.getElementById("weather");
  try {
    const d = await fetchJSON(`${API}/api/weather`);
    if (d.error) throw new Error(d.error);
    el.innerHTML = `
      <img class="weather-icon" src="https://openweathermap.org/img/wn/${d.icon}@2x.png" alt="${d.description}" />
      <div class="weather-temp">${d.temp}&thinsp;°C</div>
      <div class="weather-details">
        <span class="weather-city">${d.city}</span>
        <span class="weather-desc">${d.description}</span>
      </div>`;
  } catch(e) {
    el.innerHTML = `<span class="error" style="color:#aaa">${e.message}</span>`;
  }
}

// ── Fear & Greed Index ────────────────────────────────────────────────────────
async function loadFearGreed() {
  const el = document.getElementById("fear-greed");
  if (!el) return;
  try {
    const d = await fetchJSON("https://api.alternative.me/fng/?limit=1");
    const item = d.data[0];
    const val = parseInt(item.value);
    const label = item.value_classification;
    const color = val <= 25 ? "#dc2626"
                : val <= 45 ? "#f97316"
                : val <= 55 ? "#ca8a04"
                : val <= 75 ? "#65a30d"
                :             "#16a34a";
    el.innerHTML = `
      <div class="fg-gauge">
        <div class="fg-bar-bg">
          <div class="fg-bar-fill" style="width:${val}%;background:${color}"></div>
        </div>
      </div>
      <div class="fg-value" style="color:${color}">${val}</div>
      <div class="fg-label">${escapeHtml(label)}</div>`;
  } catch(e) {
    el.innerHTML = `<span style="color:#aaa;font-size:0.65rem">–</span>`;
  }
}

// ── Sparklines (HOME) ─────────────────────────────────────────────────────────
function sparklinePath(values, w, h) {
  if (!values || values.length < 2) return "";
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || 1;
  const step = w / (values.length - 1);
  return values.map((v, i) => {
    const x = i * step;
    const y = h - ((v - min) / range) * h;
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

let chartsRendering = false;

// ── Signale ───────────────────────────────────────────────────────────────────
async function loadSignals() {
  if (chartsRendering) return;
  try {
    const signals = await fetchJSON(`${API}/api/signals`);
    if (signals.error) return;
    if (chartsRendering) return;
    document.querySelectorAll(".chart-card[data-symbol]").forEach(card => {
      const sig = signals[card.dataset.symbol] || "neutral";
      card.classList.remove("signal-buy","signal-sell","signal-neutral");
      card.classList.add(`signal-${sig}`);
    });
  } catch(e) {}
}

// ── Balances ──────────────────────────────────────────────────────────────────
function renderBalances(id, data) {
  const el = document.getElementById(id);
  if (data.error) { el.innerHTML = `<span class="error">${escapeHtml(data.error)}</span>`; return; }
  const entries = Object.entries(data);
  if (!entries.length) { el.innerHTML = `<span class="error">Keine Bestände</span>`; return; }
  el.innerHTML = entries.map(([s, a]) => {
    const amount = parseFloat(a);
    let eurStr = "";
    if (s === "EUR") {
      eurStr = `<span class="balance-eur">${formatEur(amount)}</span>`;
    } else if (!STABLE_COINS.has(s) && Object.keys(_chartPrices).length) {
      const key = Object.keys(_chartPrices).find(k => k.startsWith(s + "/") || k === s);
      if (key) eurStr = `<span class="balance-eur">${formatEur(amount * _chartPrices[key])}</span>`;
    }
    return `
    <div class="balance-item">
      <span class="balance-symbol">${escapeHtml(s)}</span>
      <span class="balance-amount">${formatAmount(a)}</span>
      ${eurStr}
    </div>`;
  }).join("");
}

// ── News-Tab ──────────────────────────────────────────────────────────────────
let newsLoaded = false;
let newsArticles = [];
let newsActiveFilter = "all";

async function loadNewsTab() {
  newsLoaded = true;
  const list = document.getElementById("news-list");
  try {
    newsArticles = await fetchJSON(`${API}/api/news/full`);
    if (!newsArticles.length) { list.innerHTML = `<span class="error">Keine Nachrichten</span>`; return; }
    renderNewsFilter();
    renderNewsList();
  } catch(e) {
    if (!newsArticles.length) {
      list.innerHTML = `<span class="error">Nachrichten nicht verfügbar: ${e.message}</span>`;
    }
  }
}

function renderNewsFilter() {
  const filterEl = document.getElementById("news-filter");
  if (!filterEl) return;
  const sources = ["all", ...new Set(newsArticles.map(a => a.source).filter(Boolean))];
  filterEl.innerHTML = sources.map(s => `
    <button class="news-filter-btn${s === newsActiveFilter ? " active" : ""}" data-source="${escapeHtml(s)}">
      ${s === "all" ? "Alle" : escapeHtml(s)}
    </button>`).join("");
  filterEl.querySelectorAll(".news-filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      newsActiveFilter = btn.dataset.source;
      filterEl.querySelectorAll(".news-filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      renderNewsList();
    });
  });
}

function renderNewsList() {
  const list = document.getElementById("news-list");
  const filtered = newsActiveFilter === "all"
    ? newsArticles
    : newsArticles.filter(a => a.source === newsActiveFilter);
  if (!filtered.length) { list.innerHTML = `<span class="error">Keine Nachrichten für diese Quelle</span>`; return; }
  list.innerHTML = filtered.map(a => `
    <div class="news-card" data-index="${newsArticles.indexOf(a)}">
      <div class="news-card-header">
        <div class="news-card-title">${escapeHtml(a.title)}</div>
        ${a.source ? `<span class="news-card-source">${escapeHtml(a.source)}</span>` : ""}
      </div>
      <div class="news-card-summary">${escapeHtml(a.summary)}</div>
      ${a.published ? `<div class="news-card-date">${escapeHtml(a.published)}</div>` : ""}
    </div>`).join("");
  list.querySelectorAll(".news-card").forEach(card => {
    card.addEventListener("click", () => openArticle(parseInt(card.dataset.index)));
  });
}

function openArticle(i) {
  const a = newsArticles[i];
  document.getElementById("news-list").style.display = "none";
  document.getElementById("news-filter").style.display = "none";
  const detail = document.getElementById("news-detail");
  detail.style.display = "flex";
  document.getElementById("news-detail-title").textContent   = a.title;
  document.getElementById("news-detail-summary").textContent = a.summary;
  const link = document.getElementById("news-detail-link");
  link.href = a.link;
  link.style.display = a.link ? "inline" : "none";
}

document.getElementById("news-back-btn").addEventListener("click", () => {
  document.getElementById("news-detail").style.display = "none";
  document.getElementById("news-list").style.display = "flex";
  document.getElementById("news-filter").style.display = "flex";
});

// ── KI-Tab ────────────────────────────────────────────────────────────────────
let aiLoaded = false;

async function loadAI() {
  aiLoaded = true;
  const el = document.getElementById("ai-summary");
  const ts = document.getElementById("ai-timestamp");
  try {
    const data = await fetchJSON(`${API}/api/ai-summary`);
    if (data.error) { el.innerHTML = `<span class="error">${escapeHtml(data.error)}</span>`; return; }
    el.innerHTML = marked.parse(data.summary);
    ts.textContent = data.generated_at ? `Stand: ${data.generated_at}` : "";
  } catch(e) {
    el.innerHTML = `<span class="error">KI-Zusammenfassung nicht verfügbar: ${e.message}</span>`;
    aiLoaded = false;
  }
}

document.getElementById("ai-refresh-btn")?.addEventListener("click", async () => {
  const btn = document.getElementById("ai-refresh-btn");
  btn.disabled = true;
  btn.textContent = "…";
  try {
    await fetch(`${API}/api/ai-summary/refresh`, { method: "POST" });
    aiLoaded = false;
    await loadAI();
  } catch(e) {}
  btn.disabled = false;
  btn.textContent = "↺";
});

// ── RSS Ticker ────────────────────────────────────────────────────────────────
const ticker = { headlines: [], index: 0, interval: null };

async function loadTicker() {
  try {
    const headlines = await fetchJSON(`${API}/api/news`);
    if (Array.isArray(headlines) && headlines.length) {
      ticker.headlines = headlines;
      ticker.index = 0;
    }
  } catch(e) {
    if (!ticker.headlines.length) ticker.headlines = ["Newsfeed nicht verfügbar"];
  }
  if (!ticker.interval) {
    showNextHeadline();
    ticker.interval = setInterval(showNextHeadline, 30000);
  }
}

function showNextHeadline() {
  if (!ticker.headlines.length) return;
  const el = document.getElementById("ticker-headline");
  const counter = document.getElementById("ticker-counter");
  el.classList.remove("visible");
  setTimeout(() => {
    el.textContent = ticker.headlines[ticker.index];
    counter.textContent = `${ticker.index + 1} / ${ticker.headlines.length}`;
    el.classList.add("visible");
    ticker.index = (ticker.index + 1) % ticker.headlines.length;
  }, 800);
}

// ── Portfolio Gesamtwert ───────────────────────────────────────────────────────
let _chartPrices = {};
let _chartChanges = {};
let _chartPeriodLabel = "";
let _balanceAmounts = {};
let _portfolioSnapshots = [];
let _krakenData = {};
let _bitvavoData = {};

async function loadPortfolioSnapshotsBackground() {
  try {
    _portfolioSnapshots = await fetchJSON(`${API}/api/portfolio-history`);
  } catch(e) {}
}

function formatPeriod(intervalMin, candles) {
  const total = intervalMin * candles;
  if (total < 60) return `${total}min`;
  const h = Math.floor(total / 60);
  const m = total % 60;
  return m === 0 ? `${h}h` : `${h}h${m}m`;
}

const STABLE_COINS = new Set(["EUR","USDT","USDC","BUSD","DAI","TUSD"]);

function savePortfolioSnapshot(value) {
  fetch(`${API}/api/portfolio-history/add`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  }).catch(() => {});
}

async function loadCharts() {
  const section = document.getElementById("charts-section");
  chartsRendering = true;
  try {
    const data = await fetchJSON(`${API}/api/charts`);
    _chartPrices = {};
    _chartChanges = {};
    const meta = data._meta || {};
    _chartPeriodLabel = meta.interval ? formatPeriod(meta.interval, meta.candles || 25) : "";
    section.innerHTML = Object.entries(data).filter(([s]) => s !== "_meta").map(([symbol, info]) => {
      if (info.error) return `<div class="chart-card" data-symbol="${symbol}"><div class="chart-symbol">${symbol}</div><div class="error">-</div></div>`;
      _chartPrices[symbol] = info.price;
      _chartChanges[symbol] = info.change_pct;
      const up = info.change_pct >= 0;
      const path = sparklinePath(info.sparkline, 100, 26);
      const color = up ? "#16a34a" : "#dc2626";
      const baseCoin = symbol.split("/")[0].toLowerCase();
      return `<div class="chart-card" data-symbol="${escapeHtml(symbol)}">
        <div class="chart-header">
          <div class="chart-symbol-wrap">
            <img class="coin-icon" src="https://assets.coincap.io/assets/icons/${baseCoin}@2x.png"
              onerror="this.style.display='none'" alt="${baseCoin}" />
            <span class="chart-symbol">${escapeHtml(symbol.split("/")[0])}</span>
          </div>
          <span class="chart-change ${up?"up":"down"}">${up?"+":""}${info.change_pct.toFixed(2)}%${_chartPeriodLabel ? ` <span class="chart-period">${_chartPeriodLabel}</span>` : ""}</span>
        </div>
        <div class="chart-price">${formatPrice(info.price)} €</div>
        <svg class="chart-sparkline" viewBox="0 0 100 26" preserveAspectRatio="none">
          <path d="${path}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
        </svg>
      </div>`;
    }).join("");
    if (Object.keys(_krakenData).length)  renderBalances("kraken-balances",  _krakenData);
    if (Object.keys(_bitvavoData).length) renderBalances("bitvavo-balances", _bitvavoData);
    updatePortfolioTotal();
  } catch(e) {
    section.innerHTML = `<span class="error">Kurse nicht verfügbar: ${e.message}</span>`;
  } finally {
    chartsRendering = false;
  }
}

async function loadBalances() {
  try {
    const kraken  = await fetchJSON(`${API}/api/kraken`);
    const bitvavo = await fetchJSON(`${API}/api/bitvavo`);
    _krakenData  = kraken.error  ? {} : kraken;
    _bitvavoData = bitvavo.error ? {} : bitvavo;
    renderBalances("kraken-balances",  kraken);
    renderBalances("bitvavo-balances", bitvavo);
    _balanceAmounts = {};
    for (const [s, a] of Object.entries(_krakenData))  _balanceAmounts[s] = (_balanceAmounts[s] || 0) + parseFloat(a);
    for (const [s, a] of Object.entries(_bitvavoData)) _balanceAmounts[s] = (_balanceAmounts[s] || 0) + parseFloat(a);
    updatePortfolioTotal();
  } catch(e) {
    document.getElementById("kraken-balances").innerHTML  = `<span class="error">Nicht verfügbar</span>`;
    document.getElementById("bitvavo-balances").innerHTML = `<span class="error">Nicht verfügbar</span>`;
  }
}

function updatePortfolioTotal() {
  const el = document.getElementById("portfolio-total");
  if (!el) return;
  if (!Object.keys(_balanceAmounts).length || !Object.keys(_chartPrices).length) return;

  let total = 0;
  let total24hAgo = 0;
  for (const [coin, amount] of Object.entries(_balanceAmounts)) {
    if (STABLE_COINS.has(coin)) { total += amount; total24hAgo += amount; continue; }
    const key = Object.keys(_chartPrices).find(k => k.startsWith(coin + "/") || k === coin);
    if (key) {
      const val = amount * _chartPrices[key];
      total += val;
      const chg = _chartChanges[key];
      total24hAgo += chg != null ? val / (1 + chg / 100) : val;
    }
  }
  if (total <= 0) return;

  // Use actual 24h-ago snapshot if available — captures deposits/withdrawals too
  const nowTs = Date.now() / 1000;
  const past24h = _portfolioSnapshots.filter(([ts]) => ts <= nowTs - 86400);
  let diff, diffPct, periodSuffix;
  if (past24h.length > 0) {
    const refVal = past24h[past24h.length - 1][1];
    diff = total - refVal;
    diffPct = refVal > 0 ? (diff / refVal) * 100 : 0;
    periodSuffix = " · 24h";
  } else {
    diff = total - total24hAgo;
    diffPct = total24hAgo > 0 ? (diff / total24hAgo) * 100 : 0;
    periodSuffix = _chartPeriodLabel ? ` · ${_chartPeriodLabel}` : "";
  }
  const isUp = diff >= 0;
  const arrow = isUp ? "▲" : "▼";
  const sign  = isUp ? "+" : "";
  el.innerHTML = `
    <div class="portfolio-value">${total.toLocaleString("de-DE", {minimumFractionDigits: 2, maximumFractionDigits: 2})} €</div>
    <div class="portfolio-change ${isUp ? "up" : "down"}">${arrow} ${sign}${diffPct.toFixed(2)}% (${sign}${diff.toLocaleString("de-DE", {minimumFractionDigits: 2, maximumFractionDigits: 2})} €)${periodSuffix}</div>`;

  savePortfolioSnapshot(total);
}

// ── Bot-Status ─────────────────────────────────────────────────────────────────
let _prevTradeCount = null;

async function loadBotStatus() {
  const el = document.getElementById("bot-status");
  try {
    const bots = await fetchJSON(`${API}/api/bot-status`);
    if (!Array.isArray(bots) || !bots.length) {
      el.innerHTML = `<span class="bot-entry"><span class="bot-status-dot unknown"></span><span class="bot-status-text">–</span></span>`;
      return;
    }

    const totalTrades = bots.filter(b => b.available).reduce((s, b) => s + (b.open_trades || 0), 0);
    if (_prevTradeCount !== null && totalTrades !== _prevTradeCount) {
      el.classList.add("bot-trade-alert");
      setTimeout(() => el.classList.remove("bot-trade-alert"), 3000);
    }
    _prevTradeCount = totalTrades;

    el.innerHTML = bots.map((d, i) => {
      const name = escapeHtml(d.name || "Bot");
      if (!d.available) {
        return `<span class="bot-entry" title="${name}: Offline"><span class="bot-status-dot unknown"></span><span class="bot-name">${name}</span></span>`;
      }
      const running = d.state === "running";
      const dotClass = running ? "running" : "stopped";
      const tradesHtml = d.open_trades != null
        ? `<span class="bot-status-trades">${d.open_trades}/${d.max_trades || "?"}</span>`
        : "";
      return `<span class="bot-entry" title="${name}: ${escapeHtml(d.state || 'gestoppt')}"><span class="bot-status-dot ${dotClass}"></span><span class="bot-name">${name}</span>${tradesHtml}</span>`;
    }).join(`<span class="bot-sep">·</span>`);
  } catch(e) {
    el.innerHTML = `<span class="bot-entry"><span class="bot-status-dot unknown"></span><span class="bot-status-text">–</span></span>`;
  }
}

// ── Trades-Tab ─────────────────────────────────────────────────────────────────
let tradesLoaded = false;

function formatTradeDate(s) {
  if (!s) return "";
  const d = new Date(s.endsWith("Z") ? s : s + "Z");
  return d.toLocaleDateString("de-DE", {day:"2-digit",month:"2-digit"}) + " " +
         d.toLocaleTimeString("de-DE", {hour:"2-digit",minute:"2-digit"});
}

function renderTrade(t) {
  const pct = typeof t.profit_pct === "number" ? t.profit_pct : null;
  const abs = typeof t.profit_abs === "number" ? t.profit_abs : null;
  const isPos = pct != null && pct >= 0;
  const cardClass = pct == null ? "" : (isPos ? "profit-pos" : "profit-neg");
  const profitClass = pct == null ? "" : (isPos ? "pos" : "neg");
  const profitStr = pct != null
    ? `${isPos?"+":""}${pct.toFixed(2)}% (${abs != null ? (isPos?"+":"") + abs.toFixed(2) + " €" : ""})`
    : "offen";
  const buyRate  = typeof t.open_rate  === "number" ? formatPrice(t.open_rate)  : "–";
  const sellRate = typeof t.close_rate === "number" ? formatPrice(t.close_rate) : (typeof t.current_rate === "number" ? formatPrice(t.current_rate) : "–");
  const openDate  = formatTradeDate(t.open_date);
  const closeDate = t.close_date ? formatTradeDate(t.close_date) : "";
  const duration  = t.is_open ? ` · ${formatDuration(t.open_date)}` : "";
  const botBadge = t.bot ? `<span class="trade-bot">${escapeHtml(t.bot)}</span>` : "";
  return `<div class="trade-card ${cardClass}">
    <div class="trade-header">
      <span class="trade-pair">${escapeHtml(t.pair || "–")}</span>
      ${botBadge}
      <span class="trade-profit ${profitClass}">${profitStr}</span>
    </div>
    <div class="trade-meta">Kauf: ${buyRate} € → ${t.is_open ? "Aktuell" : "Verkauf"}: ${sellRate} €</div>
    <div class="trade-dates">${openDate}${closeDate ? " · " + closeDate : ""}${duration}</div>
  </div>`;
}

async function loadTrades() {
  tradesLoaded = true;
  const openEl   = document.getElementById("open-trades-list");
  const closedEl = document.getElementById("closed-trades-list");
  const statsEl  = document.getElementById("trades-stats");
  try {
    const data = await fetchJSON(`${API}/api/trades`);
    if (data.error) {
      openEl.innerHTML = closedEl.innerHTML = `<span class="error">${escapeHtml(data.error)}</span>`;
      return;
    }
    const open   = data.open   || [];
    const closed = data.closed || [];
    openEl.innerHTML   = open.length   ? open.map(renderTrade).join("")   : `<span class="loading">Keine offenen Trades</span>`;
    closedEl.innerHTML = closed.length ? closed.map(renderTrade).join("") : `<span class="loading">Keine abgeschlossenen Trades</span>`;

    if (statsEl && closed.length) {
      const wins = closed.filter(t => t.profit_pct >= 0).length;
      const winRate = ((wins / closed.length) * 100).toFixed(0);
      const totalPnl = closed.reduce((s, t) => s + (t.profit_abs || 0), 0);
      const isPos = totalPnl >= 0;
      statsEl.innerHTML = `
        <span class="trade-stat">Win-Rate: <strong>${winRate}%</strong></span>
        <span class="trade-stat-sep">·</span>
        <span class="trade-stat">Gesamt P&L: <strong class="${isPos?"pos":"neg"}">${isPos?"+":""}${totalPnl.toFixed(2)} €</strong></span>
        <span class="trade-stat-sep">·</span>
        <span class="trade-stat">${closed.length} Trades</span>`;
    }
  } catch(e) {
    openEl.innerHTML = closedEl.innerHTML = `<span class="error">Nicht verfügbar: ${e.message}</span>`;
    tradesLoaded = false;
  }
}

// ── Portfolio-Verlauf Tab ─────────────────────────────────────────────────────
let portfolioLoaded = false;
let portfolioData = [];
let portfolioRange = "7d";

async function loadPortfolioHistory() {
  portfolioLoaded = true;
  const svg = document.getElementById("portfolio-hist-chart");
  try {
    portfolioData = await fetchJSON(`${API}/api/portfolio-history`);
    renderPortfolioChart();
  } catch(e) {
    if (svg) svg.innerHTML = `<text x="50%" y="50%" text-anchor="middle" fill="#aaa" font-size="11">Nicht verfügbar: ${e.message}</text>`;
    portfolioLoaded = false;
  }
}

function renderPortfolioChart() {
  const svg    = document.getElementById("portfolio-hist-chart");
  const statsEl = document.getElementById("portfolio-hist-stats");
  if (!svg) return;

  const now = Date.now() / 1000;
  const cutoff = portfolioRange === "24h" ? now - 86400
               : portfolioRange === "7d"  ? now - 604800
               : portfolioRange === "30d" ? now - 2592000
               : 0;
  const data = cutoff > 0 ? portfolioData.filter(([ts]) => ts >= cutoff) : portfolioData;

  if (data.length < 2) {
    svg.innerHTML = `<text x="50%" y="50%" text-anchor="middle" fill="#aaa" font-size="11">Nicht genug Daten (${data.length} Einträge)</text>`;
    if (statsEl) statsEl.innerHTML = "";
    return;
  }

  const W = 760, H = 220;
  const PAD = { t: 10, r: 10, b: 28, l: 64 };
  const cW = W - PAD.l - PAD.r;
  const cH = H - PAD.t - PAD.b;

  const values = data.map(([, v]) => v);
  const times  = data.map(([ts]) => ts);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const rangeV = maxV - minV || 1;
  const minT = times[0], maxT = times[times.length - 1];

  const toX = ts => PAD.l + ((ts - minT) / (maxT - minT || 1)) * cW;
  const toY = v  => PAD.t + cH - ((v - minV) / rangeV) * cH;

  const linePath = data.map(([ts, v], i) => `${i === 0 ? "M" : "L"}${toX(ts).toFixed(1)},${toY(v).toFixed(1)}`).join(" ");
  const areaPath = linePath
    + ` L${toX(maxT).toFixed(1)},${(PAD.t + cH).toFixed(1)}`
    + ` L${toX(minT).toFixed(1)},${(PAD.t + cH).toFixed(1)} Z`;

  const lastVal  = values[values.length - 1];
  const firstVal = values[0];
  const isUp     = lastVal >= firstVal;
  const stroke   = isUp ? "#16a34a" : "#dc2626";
  const fill     = isUp ? "rgba(22,163,74,0.08)" : "rgba(220,38,38,0.08)";

  // Y-axis: 3 levels
  const yTicks = [minV, minV + rangeV * 0.5, maxV];
  const gridLines = yTicks.map(v =>
    `<line x1="${PAD.l}" y1="${toY(v).toFixed(1)}" x2="${W - PAD.r}" y2="${toY(v).toFixed(1)}" stroke="var(--border)" stroke-width="0.5"/>`
  ).join("");
  const yLabels = yTicks.map(v =>
    `<text x="${PAD.l - 4}" y="${toY(v).toFixed(1)}" text-anchor="end" dominant-baseline="middle" fill="var(--text-muted)" font-size="9">${v.toLocaleString("de-DE",{maximumFractionDigits:0})} €</text>`
  ).join("");

  // X-axis: 4 labels
  const xLabels = Array.from({length: 4}, (_, i) => {
    const ts = minT + (maxT - minT) * (i / 3);
    const d  = new Date(ts * 1000);
    return `<text x="${toX(ts).toFixed(1)}" y="${H - 4}" text-anchor="middle" fill="var(--text-muted)" font-size="9">${d.toLocaleDateString("de-DE",{day:"2-digit",month:"2-digit"})}</text>`;
  }).join("");

  const curY = toY(lastVal);
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = `
    ${gridLines}
    ${yLabels}
    ${xLabels}
    <path d="${areaPath}" fill="${fill}" stroke="none"/>
    <path d="${linePath}" fill="none" stroke="${stroke}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
    <line x1="${PAD.l}" y1="${curY.toFixed(1)}" x2="${W - PAD.r}" y2="${curY.toFixed(1)}" stroke="${stroke}" stroke-width="0.5" stroke-dasharray="3,3" opacity="0.5"/>
    <circle cx="${toX(maxT).toFixed(1)}" cy="${curY.toFixed(1)}" r="3" fill="${stroke}"/>`;

  if (statsEl) {
    const change    = lastVal - firstVal;
    const changePct = firstVal > 0 ? ((change / firstVal) * 100).toFixed(2) : "0.00";
    const sign      = change >= 0 ? "+" : "";
    const cls       = change >= 0 ? "pos" : "neg";
    statsEl.innerHTML = `
      <span class="phist-stat">Aktuell: <strong>${lastVal.toLocaleString("de-DE",{minimumFractionDigits:2,maximumFractionDigits:2})} €</strong></span>
      <span class="phist-sep">·</span>
      <span class="phist-stat">Änderung: <strong class="${cls}">${sign}${change.toLocaleString("de-DE",{minimumFractionDigits:2,maximumFractionDigits:2})} € (${sign}${changePct}%)</strong></span>
      <span class="phist-sep">·</span>
      <span class="phist-stat">Max: ${maxV.toLocaleString("de-DE",{minimumFractionDigits:2,maximumFractionDigits:2})} €</span>
      <span class="phist-sep">·</span>
      <span class="phist-stat">Min: ${minV.toLocaleString("de-DE",{minimumFractionDigits:2,maximumFractionDigits:2})} €</span>`;
  }
}

document.querySelectorAll(".range-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".range-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    portfolioRange = btn.dataset.range;
    renderPortfolioChart();
  });
});

// ── Top Movers ────────────────────────────────────────────────────────────────
const EXCLUDED_BASES = new Set([
  "USDC","BUSD","DAI","TUSD","USDP","FDUSD","USDD","UST","USDB",
  "EUR","GBP","TRY","BRL","AUD","BTC", // BTC excluded — already shown in charts
]);

async function loadTopMovers() {
  const el = document.getElementById("ind-top-movers");
  if (!el) return;
  try {
    const data = await fetchJSON("https://api.binance.com/api/v3/ticker/24hr?type=MINI");
    const movers = data
      .filter(t => {
        if (!t.symbol.endsWith("USDT")) return false;
        const base = t.symbol.slice(0, -4);
        if (EXCLUDED_BASES.has(base)) return false;
        if (/UP$|DOWN$|3L$|3S$|BEAR$|BULL$/.test(base)) return false;
        if (parseFloat(t.quoteVolume) < 1000000) return false;
        return true;
      })
      .map(t => ({
        sym: t.symbol.slice(0, -4),
        chg: ((parseFloat(t.lastPrice) - parseFloat(t.openPrice)) / parseFloat(t.openPrice)) * 100,
      }))
      .sort((a, b) => b.chg - a.chg);

    const gainers = movers.slice(0, 3);
    const losers  = movers.slice(-3).reverse();

    const row = (t, cls) =>
      `<div class="mover-row">
        <span class="mover-sym">${escapeHtml(t.sym)}</span>
        <span class="mover-chg ${cls}">${cls === "pos" ? "+" : ""}${t.chg.toFixed(1)}%</span>
      </div>`;

    el.innerHTML = `
      <div class="movers-cols">
        <div class="movers-col">${gainers.map(t => row(t, "pos")).join("")}</div>
        <div class="movers-col">${losers.map(t  => row(t, "neg")).join("")}</div>
      </div>`;
  } catch(e) { el.innerHTML = `<span class="ind-error">–</span>`; }
}

// ── Trending Coins Tab ────────────────────────────────────────────────────────
let trendsLoaded = false;

async function loadTrending() {
  trendsLoaded = true;
  const grid      = document.getElementById("trends-grid");
  const updatedEl = document.getElementById("trends-updated");
  try {
    const data  = await fetchJSON("https://api.coingecko.com/api/v3/search/trending");
    const coins = data.coins.map(c => c.item);

    if (updatedEl) {
      updatedEl.textContent = new Date().toLocaleTimeString("de-DE", {hour:"2-digit", minute:"2-digit"});
    }

    grid.innerHTML = coins.map((coin, i) => {
      const chg    = coin.data?.price_change_percentage_24h?.usd ?? null;
      const isUp   = chg != null && chg >= 0;
      const chgStr = chg != null ? `${isUp ? "+" : ""}${chg.toFixed(2)}%` : "–";
      const price  = coin.data?.price ?? "–";
      const mcap   = coin.data?.market_cap ?? "";

      return `<div class="trend-card">
        <div class="trend-top">
          <span class="trend-rank">#${i + 1}</span>
          <img class="trend-icon" src="${escapeHtml(coin.large)}"
            onerror="this.src='${escapeHtml(coin.thumb)}'" alt="${escapeHtml(coin.symbol)}" />
          <div class="trend-names">
            <span class="trend-name">${escapeHtml(coin.name)}</span>
            <span class="trend-symbol">${escapeHtml(coin.symbol.toUpperCase())}</span>
          </div>
        </div>
        <div class="trend-bottom">
          <span class="trend-price">${escapeHtml(String(price))}</span>
          <span class="trend-chg ${chg != null ? (isUp ? "up" : "down") : ""}">${chgStr}</span>
        </div>
        ${mcap ? `<div class="trend-mcap">${escapeHtml(String(mcap))}</div>` : ""}
      </div>`;
    }).join("");
  } catch(e) {
    grid.innerHTML = `<span class="error">Trending-Daten nicht verfügbar: ${e.message}</span>`;
    trendsLoaded = false;
  }
}

// ── Markt-Indikatoren ─────────────────────────────────────────────────────────
async function loadMarketIndicators() {
  loadBtcDominance();
  loadFundingRate();
  loadLongShortRatio();
  loadTotalMarketCap();
  loadTopMovers();
}

async function loadBtcDominance() {
  const el = document.getElementById("ind-btc-dom");
  if (!el) return;
  try {
    const d = await fetchJSON("https://api.coingecko.com/api/v3/global");
    const dom = d.data.market_cap_percentage.btc;
    const pct = dom.toFixed(1);
    const color = dom > 55 ? "#f97316" : dom > 45 ? "#ca8a04" : "#4c6ef5";
    const label = dom > 55 ? "BTC Season" : dom < 45 ? "Alt Season" : "Neutral";
    el.innerHTML = `
      <div class="ind-value" style="color:${color}">${pct}<span class="ind-unit">%</span></div>
      <div class="ind-bar-bg"><div class="ind-bar-fill" style="width:${pct}%;background:${color}"></div></div>
      <div class="ind-sub">${label}</div>`;
  } catch(e) { el.innerHTML = `<span class="ind-error">–</span>`; }
}

async function loadFundingRate() {
  const el = document.getElementById("ind-funding");
  if (!el) return;
  try {
    const d = await fetchJSON("https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1");
    const rate = parseFloat(d[0].fundingRate) * 100;
    const isPos = rate >= 0;
    const color = isPos ? "#16a34a" : "#dc2626";
    const sign = isPos ? "+" : "";
    const barPct = Math.min(Math.abs(rate) / 0.075 * 50, 50);
    const label = isPos ? "Longs zahlen" : "Shorts zahlen";
    el.innerHTML = `
      <div class="ind-value" style="color:${color}">${sign}${rate.toFixed(4)}<span class="ind-unit">%</span></div>
      <div class="ind-funding-wrap">
        <div class="ind-funding-fill" style="${isPos ? `left:50%;` : `right:50%;`}width:${barPct}%;background:${color}"></div>
      </div>
      <div class="ind-sub">${label}</div>`;
  } catch(e) { el.innerHTML = `<span class="ind-error">–</span>`; }
}

async function loadLongShortRatio() {
  const el = document.getElementById("ind-ls-ratio");
  if (!el) return;
  try {
    const d = await fetchJSON("https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=5m&limit=1");
    const longPct  = (parseFloat(d[0].longAccount)  * 100).toFixed(1);
    const shortPct = (parseFloat(d[0].shortAccount) * 100).toFixed(1);
    el.innerHTML = `
      <div class="ind-ls-nums">
        <span style="color:#16a34a">${longPct}%</span>
        <span style="color:#dc2626">${shortPct}%</span>
      </div>
      <div class="ind-ls-bar">
        <div style="width:${longPct}%;background:#16a34a"></div>
        <div style="width:${shortPct}%;background:#dc2626"></div>
      </div>
      <div class="ind-sub">Long &nbsp;·&nbsp; Short</div>`;
  } catch(e) { el.innerHTML = `<span class="ind-error">–</span>`; }
}

async function loadTotalMarketCap() {
  const el = document.getElementById("ind-mktcap");
  if (!el) return;
  try {
    const d = await fetchJSON("https://api.coingecko.com/api/v3/global");
    const mcap = d.data.total_market_cap.usd;
    const chg  = d.data.market_cap_change_percentage_24h_usd;
    const isUp = chg >= 0;
    const color = isUp ? "#16a34a" : "#dc2626";
    const sign  = isUp ? "+" : "";

    let mcapStr;
    if (mcap >= 1e12)      mcapStr = (mcap / 1e12).toFixed(2) + " Bio.";
    else if (mcap >= 1e9)  mcapStr = (mcap / 1e9).toFixed(0)  + " Mrd.";
    else                   mcapStr = (mcap / 1e6).toFixed(0)  + " Mio.";

    const barPct = Math.min(Math.abs(chg) / 5 * 50, 50);
    el.innerHTML = `
      <div class="ind-value" style="color:${color}">${sign}${chg.toFixed(2)}<span class="ind-unit">%</span></div>
      <div class="ind-funding-wrap">
        <div class="ind-funding-fill" style="${isUp ? `left:50%;` : `right:50%;`}width:${barPct}%;background:${color}"></div>
      </div>
      <div class="ind-sub">${mcapStr} Gesamt</div>`;
  } catch(e) { el.innerHTML = `<span class="ind-error">–</span>`; }
}

// ── Start & Intervalle ────────────────────────────────────────────────────────
const intervals = {};

loadWeather();
loadFearGreed();
loadMarketIndicators();
loadCharts().then(() => loadSignals());
loadBalances();
loadTicker();
loadBotStatus();
loadPortfolioSnapshotsBackground();

intervals.weather    = setInterval(loadWeather,          30 * 60 * 1000);
intervals.fearGreed  = setInterval(loadFearGreed,        15 * 60 * 1000);
intervals.indicators = setInterval(loadMarketIndicators, 10 * 60 * 1000);
intervals.charts    = setInterval(() => loadCharts().then(() => loadSignals()),  5 * 60 * 1000);
intervals.balances  = setInterval(loadBalances,   2 * 60 * 1000);
intervals.ticker    = setInterval(loadTicker,    15 * 60 * 1000);
intervals.botStatus = setInterval(loadBotStatus,  2 * 60 * 1000);
intervals.trades    = setInterval(() => { if (tradesLoaded)    loadTrades(); },             2 * 60 * 1000);
intervals.news      = setInterval(() => { if (newsLoaded)      loadNewsTab(); },           15 * 60 * 1000);
intervals.portfolio = setInterval(() => { if (portfolioLoaded) loadPortfolioHistory(); }, 30 * 60 * 1000);
intervals.portfolioSnaps = setInterval(loadPortfolioSnapshotsBackground, 5 * 60 * 1000);
intervals.trends    = setInterval(() => { if (trendsLoaded)    loadTrending(); },          15 * 60 * 1000);
