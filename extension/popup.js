// ShopAssist – popup.js v2.0

const API_BASE = "https://shopassist-0hud.onrender.com";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const searchInput = document.getElementById("searchInput");
const searchBtn = document.getElementById("searchBtn");
const skeletonWrap = document.getElementById("skeletonWrap");
const errorBox = document.getElementById("errorBox");
const results = document.getElementById("results");
const queryLabel = document.getElementById("queryLabel");
const amazonDiv = document.getElementById("amazonResults");
const flipkartDiv = document.getElementById("flipkartResults");
const summaryBar = document.getElementById("summaryBar");
const summaryText = document.getElementById("summaryText");
const savingsChip = document.getElementById("savingsChip");
const detectBar = document.getElementById("detectBar");
const detectName = document.getElementById("detectName");
const useDetected = document.getElementById("useDetected");
const footerStatus = document.getElementById("footerStatus");
const sortBtns = document.querySelectorAll(".sort-btn");
const priceSlider = document.getElementById("priceSlider");
const priceRangeLabel = document.getElementById("priceRangeLabel");
const filterBar = document.getElementById("filterBar");
const shareBtn = document.getElementById("shareBtn");
const historyBtn = document.getElementById("historyBtn");
const historyDropdown = document.getElementById("historyDropdown");
const historyList = document.getElementById("historyList");
const clearHistory = document.getElementById("clearHistory");
const onboarding = document.getElementById("onboarding");
const obStart = document.getElementById("obStart");
const helpBtn = document.getElementById("helpBtn");

// ── State ─────────────────────────────────────────────────────────────────────
let currentSort = "relevance";
let lastData = null;
let lastQuery = "";
let priceMax = Infinity;
let sliderMax = 200000;

// ── Onboarding ────────────────────────────────────────────────────────────────
chrome.storage.local.get(["onboarded"], (res) => {
  if (!res.onboarded) {
    onboarding.classList.remove("hidden");
  }
});
obStart.addEventListener("click", () => {
  chrome.storage.local.set({ onboarded: true });
  onboarding.classList.add("hidden");
});
helpBtn.addEventListener("click", () => {
  chrome.storage.local.remove("onboarded");
  onboarding.classList.remove("hidden");
});

// ── Search history ────────────────────────────────────────────────────────────
const HISTORY_KEY = "searchHistory";

function loadHistory(cb) {
  chrome.storage.local.get([HISTORY_KEY], (r) => cb(r[HISTORY_KEY] || []));
}
function saveToHistory(query) {
  loadHistory((hist) => {
    const updated = [
      query,
      ...hist.filter((h) => h.toLowerCase() !== query.toLowerCase()),
    ].slice(0, 8);
    chrome.storage.local.set({ [HISTORY_KEY]: updated });
  });
}
function renderHistoryDropdown() {
  loadHistory((hist) => {
    if (!hist.length) {
      historyList.innerHTML = `<div class="history-empty">No recent searches</div>`;
    } else {
      historyList.innerHTML = hist
        .map(
          (h) =>
            `<div class="history-item" data-q="${esc(h)}"><span class="history-item-icon">🕐</span>${esc(h)}</div>`,
        )
        .join("");
      historyList.querySelectorAll(".history-item").forEach((el) => {
        el.addEventListener("click", () => {
          searchInput.value = el.dataset.q;
          historyDropdown.classList.remove("open");
          doSearch(el.dataset.q);
        });
      });
    }
  });
}

historyBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  renderHistoryDropdown();
  historyDropdown.classList.toggle("open");
});
searchInput.addEventListener("focus", () => {
  renderHistoryDropdown();
  historyDropdown.classList.add("open");
});
document.addEventListener("click", (e) => {
  if (
    !e.target.closest(".search-input-wrap") &&
    !e.target.closest("#historyBtn")
  ) {
    historyDropdown.classList.remove("open");
  }
});
clearHistory.addEventListener("click", () => {
  chrome.storage.local.remove(HISTORY_KEY);
  historyList.innerHTML = `<div class="history-empty">No recent searches</div>`;
});

// ── Sort ──────────────────────────────────────────────────────────────────────
sortBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    sortBtns.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentSort = btn.dataset.sort;
    if (lastData) rerender();
  });
});

// ── Price slider ──────────────────────────────────────────────────────────────
priceSlider.addEventListener("input", () => {
  priceMax = parseInt(priceSlider.value);
  priceRangeLabel.textContent = `Up to ₹${fmt(priceMax)}`;
  if (lastData) rerender();
});

// ── Share button ──────────────────────────────────────────────────────────────
shareBtn.addEventListener("click", () => {
  if (!lastQuery) return;
  const url = `https://www.google.com/search?q=${encodeURIComponent(lastQuery + " price comparison amazon flipkart")}`;
  const text = buildShareText();
  navigator.clipboard.writeText(text).then(() => {
    shareBtn.textContent = "✓ Copied!";
    shareBtn.classList.add("copied");
    setTimeout(() => {
      shareBtn.textContent = "⎘ Share";
      shareBtn.classList.remove("copied");
    }, 2000);
  });
});

function buildShareText() {
  if (!lastData) return "";
  const lines = [`🛒 ShopAssist — Price Comparison for "${lastQuery}"\n`];
  const amz = (lastData.amazon || []).slice(0, 2);
  const fk = (lastData.flipkart || []).slice(0, 2);
  if (amz.length) {
    lines.push("📦 Amazon:");
    amz.forEach((p) =>
      lines.push(`  • ${p.name?.slice(0, 50)} — ${p.price || "N/A"}`),
    );
  }
  if (fk.length) {
    lines.push("🛍️ Flipkart:");
    fk.forEach((p) =>
      lines.push(`  • ${p.name?.slice(0, 50)} — ${p.price || "N/A"}`),
    );
  }
  const allP = getAllPrices(lastData);
  if (allP.length >= 2) {
    const savings = Math.max(...allP) - Math.min(...allP);
    if (savings > 0)
      lines.push(
        `\n💰 Save up to ₹${fmt(savings)} by choosing the right platform!`,
      );
  }
  return lines.join("\n");
}

// ── Auto-detect ───────────────────────────────────────────────────────────────
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  const tab = tabs[0];
  if (!tab) return;
  chrome.tabs.sendMessage(tab.id, { type: "GET_PRODUCT" }, (response) => {
    if (chrome.runtime.lastError || !response?.name) return;
    detectName.textContent = response.name;
    detectBar.classList.add("visible");
    useDetected.addEventListener("click", () => {
      searchInput.value = response.name;
      detectBar.classList.remove("visible");
      doSearch(response.name);
    });
  });
});

// ── Search ────────────────────────────────────────────────────────────────────
searchBtn.addEventListener("click", () => {
  const q = searchInput.value.trim();
  if (q) doSearch(q);
});
searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    historyDropdown.classList.remove("open");
    const q = searchInput.value.trim();
    if (q) doSearch(q);
  }
  if (e.key === "Escape") historyDropdown.classList.remove("open");
});

async function doSearch(query) {
  lastQuery = query;
  setState("loading", query);
  historyDropdown.classList.remove("open");
  try {
    const res = await fetch(
      `${API_BASE}/compare?q=${encodeURIComponent(query)}`,
      { signal: AbortSignal.timeout(25000) },
    );
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const data = await res.json();
    saveToHistory(query);
    savePriceHistory(data);
    renderResults(data, query);
  } catch (err) {
    if (err.name === "TimeoutError") {
      showError(
        "Request timed out.\n\nMake sure the backend is running:\nuvicorn main:app --reload --port 8000",
      );
    } else if (
      err.message.includes("Failed to fetch") ||
      err.message.includes("NetworkError")
    ) {
      showError(
        "Cannot connect to backend.\n\n▸ cd backend\n▸ source venv/Scripts/activate\n▸ uvicorn main:app --reload --port 8000",
      );
    } else {
      showError(err.message);
    }
  }
}

// ── State management ──────────────────────────────────────────────────────────
function setState(state, query = "") {
  skeletonWrap.classList.remove("visible");
  errorBox.classList.remove("visible");
  results.classList.remove("visible");
  filterBar.style.display = "none";
  summaryBar.style.display = "none";
  searchBtn.disabled = state === "loading";
  footerStatus.textContent = state === "loading" ? "Fetching…" : "Ready";
  if (state === "loading") skeletonWrap.classList.add("visible");
}

function showError(msg) {
  setState("idle");
  errorBox.textContent = msg;
  errorBox.classList.add("visible");
  footerStatus.textContent = "Error";
}

// ── Deduplicate ───────────────────────────────────────────────────────────────
function dedupe(products) {
  const seen = new Set();
  return products.filter((p) => {
    const key = (p.name || "")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "")
      .slice(0, 40);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

// ── Sort ──────────────────────────────────────────────────────────────────────
function sortProducts(products, sortKey) {
  const arr = [...products];
  if (sortKey === "price-asc")
    arr.sort(
      (a, b) =>
        (parsePrice(a.price) || Infinity) - (parsePrice(b.price) || Infinity),
    );
  if (sortKey === "price-desc")
    arr.sort((a, b) => (parsePrice(b.price) || 0) - (parsePrice(a.price) || 0));
  if (sortKey === "rating")
    arr.sort(
      (a, b) => (parseFloat(b.rating) || 0) - (parseFloat(a.rating) || 0),
    );
  return arr;
}

function filterByPrice(products) {
  return products.filter((p) => {
    const n = parsePrice(p.price);
    return isNaN(n) || n <= priceMax;
  });
}

function rerender() {
  const allPrices = getAllPrices(lastData);
  const minPrice = allPrices.length ? Math.min(...allPrices) : null;
  renderPlatform(
    amazonDiv,
    filterByPrice(sortProducts(dedupe(lastData.amazon || []), currentSort)),
    minPrice,
    "amazon",
  );
  renderPlatform(
    flipkartDiv,
    filterByPrice(sortProducts(dedupe(lastData.flipkart || []), currentSort)),
    minPrice,
    "flipkart",
  );
}

// ── Render results ────────────────────────────────────────────────────────────
function renderResults(data, query) {
  setState("idle");
  lastData = data;
  data.amazon = dedupe(data.amazon || []);
  data.flipkart = dedupe(data.flipkart || []);

  currentSort = "relevance";
  sortBtns.forEach((b) =>
    b.classList.toggle("active", b.dataset.sort === "relevance"),
  );

  const allPrices = getAllPrices(data);
  if (allPrices.length && priceSlider) {
    sliderMax = Math.ceil(Math.max(...allPrices) / 10000) * 10000 + 10000;
    priceMax = sliderMax;
    priceSlider.max = sliderMax;
    priceSlider.value = sliderMax;
    priceSlider.min = Math.max(
      0,
      Math.floor(Math.min(...allPrices) / 10000) * 10000,
    );
    priceRangeLabel.textContent = `Up to ₹${fmt(priceMax)}`;
    filterBar.style.display = "flex";
  }

  queryLabel.textContent = `"${query}"`;
  const minPrice = allPrices.length ? Math.min(...allPrices) : null;
  renderPlatform(amazonDiv, data.amazon, minPrice, "amazon");
  renderPlatform(flipkartDiv, data.flipkart, minPrice, "flipkart");

  if (minPrice !== null && allPrices.length >= 2) {
    const maxPrice = Math.max(...allPrices);
    const savings = maxPrice - minPrice;
    const pct = ((savings / maxPrice) * 100).toFixed(0);
    const cheapestSrc = isAmazonCheaper(data, minPrice) ? "Amazon" : "Flipkart";
    summaryText.innerHTML = `Best deal on <strong>${cheapestSrc}</strong> · Save up to`;
    savingsChip.textContent =
      savings > 0 ? `₹${fmt(savings)} (${pct}%)` : "Same price";
    summaryBar.style.display = "flex";
  }

  results.classList.add("visible");
  footerStatus.textContent = `${data.amazon.length + data.flipkart.length} results`;
}

function renderPlatform(container, products, minPrice, platform) {
  container.innerHTML = "";
  if (!products.length) {
    const label = platform === "amazon" ? "Amazon" : "Flipkart";
    const reason = priceMax < Infinity ? "in this price range" : "";
    container.innerHTML = `
      <div class="no-results">
        <div class="no-results-icon">${platform === "amazon" ? "📦" : "🛍️"}</div>
        <div class="no-results-title">Nothing on ${label} ${reason}</div>
        <div class="no-results-sub">Try a different search term${priceMax < Infinity ? " or adjust the price filter" : ""}</div>
      </div>`;
    return;
  }
  products.slice(0, 3).forEach((p) => {
    const priceNum = parsePrice(p.price);
    const isCheapest = minPrice !== null && priceNum === minPrice;
    const trendHtml = buildTrendHtml(p.name, priceNum);
    const card = document.createElement("a");
    card.className = "product-card" + (isCheapest ? " best-deal" : "");
    card.href = p.url || "#";
    card.target = "_blank";
    card.rel = "noopener noreferrer";
    const imgHtml = p.image
      ? `<img class="product-img" src="${esc(p.image)}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="product-img-placeholder" style="display:none">🛍️</div>`
      : `<div class="product-img-placeholder">🛍️</div>`;
    card.innerHTML = `
      ${imgHtml}
      <div class="product-info">
        <div class="product-name">${esc(p.name || "Product")}</div>
        <div class="product-bottom">
          <div class="price-row">
            <span class="product-price${isCheapest ? " cheapest" : ""}">${esc(p.price || "N/A")}</span>
            ${trendHtml}
          </div>
          <div style="display:flex;align-items:center;gap:6px">
            ${p.rating ? `<div class="product-rating"><span class="star">★</span>${esc(p.rating)}</div>` : ""}
            ${isCheapest ? `<span class="best-badge">Best Deal</span>` : ""}
          </div>
        </div>
      </div>`;
    container.appendChild(card);
  });
}

// ── Price History ─────────────────────────────────────────────────────────────
const PRICE_HISTORY_KEY = "priceHistory";

function priceKey(name) {
  return (name || "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "")
    .slice(0, 35);
}

function savePriceHistory(data) {
  chrome.storage.local.get([PRICE_HISTORY_KEY], (res) => {
    const history = res[PRICE_HISTORY_KEY] || {};
    const now = Date.now();
    [...(data.amazon || []), ...(data.flipkart || [])].forEach((p) => {
      const price = parsePrice(p.price);
      if (isNaN(price)) return;
      const key = priceKey(p.name);
      if (!history[key]) history[key] = [];
      const last = history[key][history[key].length - 1];
      if (!last || last.price !== price || now - last.ts > 3600000) {
        history[key].push({ price, ts: now });
      }
      if (history[key].length > 30) history[key] = history[key].slice(-30);
    });
    chrome.storage.local.set({ [PRICE_HISTORY_KEY]: history });
    window._historyCache = history;
  });
}

function buildTrendHtml(name, currentPrice) {
  const h = window._historyCache
    ? window._historyCache[priceKey(name)] || []
    : [];
  if (h.length < 2) return "";
  const prev = h[h.length - 2].price;
  if (prev === currentPrice) return `<span class="trend-flat">→</span>`;
  if (currentPrice < prev)
    return `<span class="trend-down">↓ ₹${fmt(prev - currentPrice)}</span>`;
  return `<span class="trend-up">↑ ₹${fmt(currentPrice - prev)}</span>`;
}

chrome.storage.local.get([PRICE_HISTORY_KEY], (r) => {
  window._historyCache = r[PRICE_HISTORY_KEY] || {};
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function getAllPrices(data) {
  return [...(data.amazon || []), ...(data.flipkart || [])]
    .map((p) => p.price)
    .filter(Boolean)
    .map(parsePrice)
    .filter((n) => !isNaN(n));
}
function parsePrice(str) {
  if (!str) return NaN;
  return parseFloat(String(str).replace(/[^\d.]/g, ""));
}
function fmt(n) {
  return Number(n).toLocaleString("en-IN");
}
function esc(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}
function isAmazonCheaper(data, minPrice) {
  return (data.amazon || []).some((p) => parsePrice(p.price) === minPrice);
}
