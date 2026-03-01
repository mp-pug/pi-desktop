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

// ── Kalender ──────────────────────────────────────────────────────────────────
async function loadCalendar() {
  const el = document.getElementById("calendar-list");
  try {
    const events = await fetchJSON(`${API}/api/calendar`);
    if (!Array.isArray(events) || events.length === 0) {
      el.innerHTML = `<div class="no-events">Keine Termine heute</div>`;
      return;
    }
    el.innerHTML = events.map(ev => `
      <div class="event-item">
        <div class="event-time">${ev.time}</div>
        <div class="event-title">${escapeHtml(ev.title)}</div>
      </div>
    `).join("");
  } catch (e) {
    el.innerHTML = `<span class="error">Kalender nicht verfügbar</span>`;
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
async function loadTicker() {
  const track = document.getElementById("ticker-track");
  try {
    const headlines = await fetchJSON(`${API}/api/news`);
    if (!Array.isArray(headlines) || headlines.length === 0) {
      track.innerHTML = `<span>Keine Nachrichten verfügbar</span>`;
      return;
    }
    // Doppelter Satz für nahtloses Scrollen
    const items = headlines.map(h => `<span>${escapeHtml(h)}</span>`).join("");
    track.innerHTML = items + items;

    // Animationsdauer dynamisch: ~120px pro Sekunde
    const totalWidth = track.scrollWidth / 2;
    const duration = Math.max(30, totalWidth / 80);
    track.style.animationDuration = `${duration}s`;
  } catch (e) {
    track.innerHTML = `<span>Newsfeed nicht verfügbar</span>`;
  }
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
loadCalendar();
loadBalances();
loadTicker();

// Wetter alle 10 Minuten
setInterval(loadWeather, 10 * 60 * 1000);
// Kalender alle 5 Minuten
setInterval(loadCalendar, 5 * 60 * 1000);
// Kontostände alle 2 Minuten
setInterval(loadBalances, 2 * 60 * 1000);
// Newsfeed alle 15 Minuten
setInterval(loadTicker, 15 * 60 * 1000);
