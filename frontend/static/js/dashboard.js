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
    // Lazy-load beim ersten Öffnen
    if (btn.dataset.tab === "strategy" && !strategyLoaded) loadStrategy();
    if (btn.dataset.tab === "news"     && !newsLoaded)     loadNewsTab();
    if (btn.dataset.tab === "ai"       && !aiLoaded)       loadAI();
  });
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
        <span class="weather-meta">Gefühlt ${d.feels_like}°C · ${d.humidity}% · ${d.wind_speed} km/h</span>
      </div>`;
  } catch(e) {
    el.innerHTML = `<span class="error" style="color:#aaa">${e.message}</span>`;
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

// Guard gegen Race Condition: verhindert dass loadSignals läuft während Charts neu gerendert werden
let chartsRendering = false;

async function loadCharts() {
  const section = document.getElementById("charts-section");
  chartsRendering = true;
  try {
    const data = await fetchJSON(`${API}/api/charts`);
    section.innerHTML = Object.entries(data).map(([symbol, info]) => {
      if (info.error) return `<div class="chart-card" data-symbol="${symbol}"><div class="chart-symbol">${symbol}</div><div class="error">-</div></div>`;
      const up = info.change_pct >= 0;
      const path = sparklinePath(info.sparkline, 100, 26);
      const color = up ? "#16a34a" : "#dc2626";
      return `<div class="chart-card" data-symbol="${escapeHtml(symbol)}">
        <div class="chart-header">
          <span class="chart-symbol">${escapeHtml(symbol)}</span>
          <span class="chart-change ${up?"up":"down"}">${up?"+":""}${info.change_pct.toFixed(2)}%</span>
        </div>
        <div class="chart-price">${formatPrice(info.price)} €</div>
        <svg class="chart-sparkline" viewBox="0 0 100 26" preserveAspectRatio="none">
          <path d="${path}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
        </svg>
      </div>`;
    }).join("");
  } catch(e) {
    section.innerHTML = `<span class="error">Kurse nicht verfügbar: ${e.message}</span>`;
  } finally {
    chartsRendering = false;
  }
}

// ── Signale ───────────────────────────────────────────────────────────────────
async function loadSignals() {
  // Race Condition vermeiden: nicht während Charts neu gerendert werden
  if (chartsRendering) return;
  try {
    const signals = await fetchJSON(`${API}/api/signals`);
    if (signals.error) return;
    // Nochmals prüfen: Charts könnten während des awaits neu gerendert worden sein
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
  el.innerHTML = entries.map(([s, a]) => `
    <div class="balance-item">
      <span class="balance-symbol">${escapeHtml(s)}</span>
      <span class="balance-amount">${formatAmount(a)}</span>
    </div>`).join("");
}

async function loadBalances() {
  try { renderBalances("kraken-balances",  await fetchJSON(`${API}/api/kraken`));  } catch(e) { document.getElementById("kraken-balances").innerHTML  = `<span class="error">Nicht verfügbar</span>`; }
  try { renderBalances("bitvavo-balances", await fetchJSON(`${API}/api/bitvavo`)); } catch(e) { document.getElementById("bitvavo-balances").innerHTML = `<span class="error">Nicht verfügbar</span>`; }
}

// ── Strategie Info-Button ─────────────────────────────────────────────────────
let strategyInfoLoaded = false;

document.getElementById("strategy-info-btn").addEventListener("click", () => {
  const box = document.getElementById("strategy-infobox");
  const isVisible = box.style.display !== "none";
  box.style.display = isVisible ? "none" : "block";
  if (!isVisible && !strategyInfoLoaded) loadStrategyInfo();
});

async function loadStrategyInfo() {
  strategyInfoLoaded = true;
  const el = document.getElementById("strategy-infobox-content");
  try {
    const data = await fetchJSON(`${API}/api/strategy-info`);
    if (data.error) {
      el.innerHTML = `<span class="error">${escapeHtml(data.error)}</span>`;
      strategyInfoLoaded = false; // Retry beim nächsten Öffnen
      return;
    }
    if (data.filename) {
      document.getElementById("strategy-name").textContent = data.filename.replace(".py","");
    }
    el.innerHTML = marked.parse(data.description);
  } catch(e) {
    el.innerHTML = `<span class="error">Nicht verfügbar: ${e.message}</span>`;
    strategyInfoLoaded = false;
  }
}

// ── Strategie-Tab ─────────────────────────────────────────────────────────────
let strategyLoaded = false;

async function loadStrategy() {
  strategyLoaded = true;
  const grid = document.getElementById("strategy-grid");
  const warningEl = document.getElementById("strategy-warning");
  try {
    const data = await fetchJSON(`${API}/api/strategy`);
    if (data.error) { grid.innerHTML = `<span class="error">${escapeHtml(data.error)}</span>`; return; }

    // Strategie-Mismatch-Warnung anzeigen
    if (data._warning) {
      warningEl.textContent = `⚠ ${data._warning}`;
      warningEl.style.display = "block";
    } else {
      warningEl.style.display = "none";
    }

    grid.innerHTML = Object.entries(data)
      .filter(([symbol]) => !symbol.startsWith("_"))
      .map(([symbol, info]) => {
        if (info.error) return `<div class="strategy-card">
          <div class="strategy-card-header"><span class="strategy-symbol">${symbol}</span></div>
          <div class="error">${escapeHtml(info.error)}</div>
        </div>`;

        if (!info.indicators || info.indicators.length === 0) return `<div class="strategy-card">
          <div class="strategy-card-header">
            <span class="strategy-symbol">${symbol}</span>
            <span class="strategy-signal neutral">Neutral</span>
          </div>
          <div class="strategy-no-data">Noch keine Daten (warte auf Kerzenschluss)</div>
        </div>`;

        const sig = info.signal;
        const sigLabel = sig === "buy" ? "Kaufsignal" : sig === "sell" ? "Verkaufsignal" : "Neutral";
        const indicators = info.indicators.map(ind => `
          <div class="indicator-row">
            <span class="indicator-name" title="${escapeHtml(ind.name)}">${escapeHtml(ind.name)}</span>
            <span class="indicator-value">${typeof ind.value === "number" ? ind.value.toFixed(4) : escapeHtml(String(ind.value))}</span>
            <div class="indicator-light ${ind.status}"></div>
          </div>`).join("");

        return `<div class="strategy-card">
          <div class="strategy-card-header">
            <span class="strategy-symbol">${escapeHtml(symbol)}</span>
            <span class="strategy-signal ${sig}">${sigLabel}</span>
          </div>
          <div class="strategy-counter">${info.buy_count} von ${info.total} Signalen erfüllt${info.in_trade ? " · Position offen" : ""}</div>
          <div class="indicator-list">${indicators}</div>
        </div>`;
      }).join("");
  } catch(e) {
    grid.innerHTML = `<span class="error">Strategie-Daten nicht verfügbar: ${e.message}</span>`;
  }
}

// ── News-Tab ──────────────────────────────────────────────────────────────────
let newsLoaded = false;
let newsArticles = [];

async function loadNewsTab() {
  newsLoaded = true;
  const list = document.getElementById("news-list");
  try {
    newsArticles = await fetchJSON(`${API}/api/news/full`);
    if (!newsArticles.length) { list.innerHTML = `<span class="error">Keine Nachrichten</span>`; return; }
    list.innerHTML = newsArticles.map((a, i) => `
      <div class="news-card" data-index="${i}">
        <div class="news-card-title">${escapeHtml(a.title)}</div>
        <div class="news-card-summary">${escapeHtml(a.summary)}</div>
        ${a.published ? `<div class="news-card-date">${escapeHtml(a.published)}</div>` : ""}
      </div>`).join("");

    list.querySelectorAll(".news-card").forEach(card => {
      card.addEventListener("click", () => openArticle(parseInt(card.dataset.index)));
    });
  } catch(e) {
    list.innerHTML = `<span class="error">Nachrichten nicht verfügbar: ${e.message}</span>`;
  }
}

function openArticle(i) {
  const a = newsArticles[i];
  document.getElementById("news-list").style.display = "none";
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
  }
}

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

// ── Start & Intervalle ────────────────────────────────────────────────────────
// Interval-IDs gespeichert, damit sie ggf. bereinigt werden können
const intervals = {};

loadWeather();
loadCharts().then(() => loadSignals());
loadBalances();
loadTicker();

// Signals werden nach Charts geladen (chain) – kein separater Interval nötig,
// um Race Conditions beim DOM-Neuaufbau zu vermeiden.
intervals.weather   = setInterval(loadWeather,  30 * 60 * 1000);
intervals.charts    = setInterval(() => loadCharts().then(() => loadSignals()),  5 * 60 * 1000);
intervals.balances  = setInterval(loadBalances,  2 * 60 * 1000);
intervals.ticker    = setInterval(loadTicker,   15 * 60 * 1000);
