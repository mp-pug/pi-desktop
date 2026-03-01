const API = "";

const DAYS = ["Sonntag","Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag"];
const MONTHS = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"];

// ── Uhr ───────────────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, "0");
  const m = String(now.getMinutes()).padStart(2, "0");
  const s = String(now.getSeconds()).padStart(2, "0");
  document.getElementById("clock").textContent = `${h}:${m}:${s}`;

  const day = DAYS[now.getDay()];
  const date = now.getDate();
  const month = MONTHS[now.getMonth()];
  const year = now.getFullYear();
  document.getElementById("date-display").textContent = `${day}, ${date}. ${month} ${year}`;
}
setInterval(updateClock, 1000);
updateClock();

// ── Hilfsfunktion ─────────────────────────────────────────────────────────────
async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Wetter ────────────────────────────────────────────────────────────────────
async function loadWeather() {
  const el = document.getElementById("weather");
  try {
    const d = await fetchJSON(`${API}/api/weather`);
    if (d.error) throw new Error(d.error);
    el.innerHTML = `
      <img class="weather-icon"
           src="https://openweathermap.org/img/wn/${d.icon}@2x.png"
           alt="${d.description}" />
      <div class="weather-temp">${d.temp}&thinsp;°C</div>
      <div class="weather-details">
        <span class="weather-city">${d.city}</span>
        <span class="weather-desc">${d.description}</span>
        <span class="weather-meta">
          Gefühlt ${d.feels_like}°C &nbsp;·&nbsp;
          Luftfeuchtigkeit ${d.humidity}% &nbsp;·&nbsp;
          Wind ${d.wind_speed} km/h
        </span>
      </div>
    `;
  } catch (e) {
    el.innerHTML = `<span class="error">Wetter nicht verfügbar: ${e.message}</span>`;
  }
}

// ── Kursdiagramme ─────────────────────────────────────────────────────────────
function sparklinePath(values, w, h) {
  if (!values || values.length < 2) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = w / (values.length - 1);
  return values.map((v, i) => {
    const x = i * step;
    const y = h - ((v - min) / range) * h;
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

async function loadCharts() {
  const section = document.getElementById("charts-section");
  try {
    const data = await fetchJSON(`${API}/api/charts`);
    const cards = Object.entries(data).map(([symbol, info]) => {
      if (info.error) {
        return `<div class="chart-card">
          <div class="chart-symbol">${escapeHtml(symbol)}</div>
          <div class="error" style="font-size:0.65rem">-</div>
        </div>`;
      }
      const up = info.change_pct >= 0;
      const changeStr = `${up ? "+" : ""}${info.change_pct.toFixed(2)}%`;
      const priceStr = formatPrice(info.price);
      const path = sparklinePath(info.sparkline, 100, 32);
      const color = up ? "#16a34a" : "#dc2626";
      return `<div class="chart-card" data-symbol="${escapeHtml(symbol)}">
        <div class="chart-header">
          <span class="chart-symbol">${escapeHtml(symbol)}</span>
          <span class="chart-change ${up ? "up" : "down"}">${changeStr}</span>
        </div>
        <div class="chart-price">${priceStr} €</div>
        <svg class="chart-sparkline" viewBox="0 0 100 32" preserveAspectRatio="none">
          <path d="${path}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
        </svg>
      </div>`;
    }).join("");
    section.innerHTML = cards;
  } catch (e) {
    section.innerHTML = `<span class="error">Kurse nicht verfügbar: ${e.message}</span>`;
  }
}

function formatPrice(n) {
  if (n >= 1000) return n.toLocaleString("de-DE", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  if (n >= 1)    return n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return n.toLocaleString("de-DE", { minimumFractionDigits: 4, maximumFractionDigits: 6 });
}

// ── Freqtrade Signale ─────────────────────────────────────────────────────────
async function loadSignals() {
  try {
    const signals = await fetchJSON(`${API}/api/signals`);
    if (signals.error) return; // Freqtrade nicht konfiguriert oder nicht erreichbar
    document.querySelectorAll(".chart-card[data-symbol]").forEach(card => {
      const symbol = card.dataset.symbol;
      card.classList.remove("signal-buy", "signal-sell", "signal-neutral");
      const sig = signals[symbol] || "neutral";
      card.classList.add(`signal-${sig}`);
    });
  } catch (e) {
    // Freqtrade nicht erreichbar – kein Fehler anzeigen, Karten bleiben ungefärbt
  }
}

// ── Kontostände ───────────────────────────────────────────────────────────────
function renderBalances(containerId, data) {
  const el = document.getElementById(containerId);
  if (data.error) {
    el.innerHTML = `<span class="error">${escapeHtml(data.error)}</span>`;
    return;
  }
  const entries = Object.entries(data);
  if (entries.length === 0) {
    el.innerHTML = `<span class="error">Keine Bestände</span>`;
    return;
  }
  el.innerHTML = entries.map(([symbol, amount]) => `
    <div class="balance-item">
      <span class="balance-symbol">${escapeHtml(symbol)}</span>
      <span class="balance-amount">${formatAmount(amount)}</span>
    </div>
  `).join("");
}

async function loadBalances() {
  try {
    const kraken = await fetchJSON(`${API}/api/kraken`);
    renderBalances("kraken-balances", kraken);
  } catch (e) {
    document.getElementById("kraken-balances").innerHTML =
      `<span class="error">Nicht verfügbar</span>`;
  }
  try {
    const bitvavo = await fetchJSON(`${API}/api/bitvavo`);
    renderBalances("bitvavo-balances", bitvavo);
  } catch (e) {
    document.getElementById("bitvavo-balances").innerHTML =
      `<span class="error">Nicht verfügbar</span>`;
  }
}

// ── RSS Ticker ────────────────────────────────────────────────────────────────
const ticker = {
  headlines: [],
  index: 0,
  interval: null,
};

async function loadTicker() {
  try {
    const headlines = await fetchJSON(`${API}/api/news`);
    if (Array.isArray(headlines) && headlines.length > 0) {
      ticker.headlines = headlines;
      ticker.index = 0;
    }
  } catch (e) {
    if (ticker.headlines.length === 0) {
      ticker.headlines = ["Newsfeed nicht verfügbar"];
    }
  }
  // Ticker-Loop starten (nur beim ersten Aufruf)
  if (!ticker.interval) {
    showNextHeadline();
    ticker.interval = setInterval(showNextHeadline, 30000);
  }
}

function showNextHeadline() {
  if (ticker.headlines.length === 0) return;
  const el = document.getElementById("ticker-headline");
  const counter = document.getElementById("ticker-counter");

  // Ausblenden
  el.classList.remove("visible");

  setTimeout(() => {
    el.textContent = ticker.headlines[ticker.index];
    counter.textContent = `${ticker.index + 1} / ${ticker.headlines.length}`;
    // Einblenden
    el.classList.add("visible");
    ticker.index = (ticker.index + 1) % ticker.headlines.length;
  }, 800); // nach der fade-out Transition
}

// ── Hilfsfunktionen ───────────────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatAmount(num) {
  const n = parseFloat(num);
  if (n >= 1) return n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 6 });
  return n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 8 });
}

// ── Initialisierung & Refresh-Intervalle ──────────────────────────────────────
loadWeather();
// Kurse laden, danach sofort Signale anwenden
loadCharts().then(() => loadSignals());
loadBalances();
loadTicker();

// Wetter alle 30 Minuten (max. ~48 Anfragen/Tag, bleibt unter dem Limit von 50)
setInterval(loadWeather, 30 * 60 * 1000);
// Kurse alle 5 Minuten, danach Signale aktualisieren
setInterval(() => loadCharts().then(() => loadSignals()), 5 * 60 * 1000);
// Signale alle 2 Minuten extra aktualisieren (ohne Charts neu zu laden)
setInterval(loadSignals, 2 * 60 * 1000);
// Kontostände alle 2 Minuten
setInterval(loadBalances, 2 * 60 * 1000);
// Newsfeed alle 15 Minuten
setInterval(loadTicker, 15 * 60 * 1000);
