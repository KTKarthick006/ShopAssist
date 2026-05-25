import asyncio, re, random, urllib.parse, json
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="ShopAssist API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

class Product(BaseModel):
    name: str
    price: Optional[str] = None
    rating: Optional[str] = None
    image: Optional[str] = None
    url: Optional[str] = None
    platform: str

class CompareResponse(BaseModel):
    query: str
    amazon: list[Product]
    flipkart: list[Product]

TIMEOUT = httpx.Timeout(20.0)

def amazon_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.amazon.in/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Cache-Control": "max-age=0",
    }

def flipkart_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.flipkart.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


# ── Amazon ─────────────────────────────────────────────────────────────────

async def scrape_amazon(query: str) -> list[Product]:
    encoded = urllib.parse.quote_plus(query)
    url = f"https://www.amazon.in/s?k={encoded}"

    async with httpx.AsyncClient(headers=amazon_headers(), timeout=TIMEOUT, follow_redirects=True) as client:
        try:
            await client.get("https://www.amazon.in/", timeout=10)
        except Exception:
            pass
        await asyncio.sleep(random.uniform(0.4, 1.0))
        resp = await client.get(url)

    soup = BeautifulSoup(resp.text, "lxml")
    products: list[Product] = []
    cards = soup.select("div[data-component-type='s-search-result']")
    print(f"[Amazon] {len(cards)} cards")

    for item in cards[:10]:
        try:
            # ── Name ──
            # Priority 1: organic card h2 has aria-label with full title
            h2 = item.select_one("h2")
            name = h2.get("aria-label", "").strip() if h2 else ""

            # Priority 2: sponsored cards — full title in an unclassed <span>
            SKIP = ("seeing this ad", "relevance to your search", "let us know")
            if not name or len(name) < 10:
                for span in item.select("span"):
                    cls = span.get("class") or []
                    t = span.get_text(strip=True)
                    if (not cls and 20 < len(t) < 300
                            and not any(p in t.lower() for p in SKIP)):
                        name = t
                        break

            # Priority 3: non-sspa <a> link text
            if not name or len(name) < 10:
                for a in item.select("a[href]"):
                    t = a.get_text(strip=True)
                    href = a.get("href", "")
                    if (len(t) > 20 and "/sspa/" not in href
                            and not any(p in t.lower() for p in SKIP)):
                        name = t
                        break

            if not name or len(name) < 5:
                continue

            # ── Price ──
            price_el = item.select_one("span.a-price span.a-offscreen")
            price = price_el.get_text(strip=True) if price_el else None
            if not price:
                continue  # skip unavailable items

            # ── Rating ──
            rating_el = item.select_one("span.a-icon-alt")
            rating_raw = rating_el.get_text(strip=True) if rating_el else ""
            m = re.search(r"[\d.]+", rating_raw)
            rating = m.group() if m else None

            # ── Image ──
            img_el = item.select_one("img.s-image")
            image = img_el.get("src") if img_el else None

            # ── URL ──
            full_url = None
            # First pass: prefer clean organic /dp/ links
            for a in item.select("a[href]"):
                href = a.get("href", "")
                if "/dp/" in href and "/sspa/" not in href:
                    path = href.split("/ref=")[0]
                    full_url = "https://www.amazon.in" + path
                    break

            # Second pass: sponsored cards — find ASIN from data-asin attribute
            if not full_url:
                asin = item.get("data-asin", "")
                if asin:
                    full_url = f"https://www.amazon.in/dp/{asin}"

            # Third pass: extract ASIN from /sspa/ encoded URL
            if not full_url:
                for a in item.select("a[href]"):
                    href = a.get("href", "")
                    if "/sspa/" in href:
                        asin_match = re.search(r"/dp/([A-Z0-9]{10})", href)
                        if asin_match:
                            full_url = f"https://www.amazon.in/dp/{asin_match.group(1)}"
                            break

            products.append(Product(name=name, price=price, rating=rating,
                                    image=image, url=full_url, platform="amazon"))

            if len(products) >= 5:
                break

        except Exception as e:
            print(f"[Amazon] parse error: {e}")

    print(f"[Amazon] {len(products)} parsed")
    return products


# ── Flipkart (via unofficial search API) ───────────────────────────────────

def scrape_flipkart_selenium(query: str) -> list[Product]:
    """Use Selenium (real Chrome) to bypass Flipkart CAPTCHA."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import time

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    products = []

    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.flipkart.com/search?q={encoded}&otracker=search"
        driver.get(url)

        # Close login popup if it appears
        try:
            close_btn = WebDriverWait(driver, 4).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'✕') or contains(@class,'_2KpZ6l')]"))
            )
            close_btn.click()
        except Exception:
            pass

        time.sleep(2)
        html = driver.page_source
        print(f"[Flipkart Selenium] page size={len(html)} captcha={'captcha' in html.lower()}")
        products = parse_flipkart_html(html)
    except Exception as e:
        print(f"[Flipkart Selenium] error: {e}")
    finally:
        driver.quit()

    return products


async def scrape_flipkart(query: str) -> list[Product]:
    """Run Selenium in a thread so it doesn't block the async event loop."""
    try:
        products = await asyncio.get_event_loop().run_in_executor(
            None, scrape_flipkart_selenium, query
        )
    except Exception as e:
        print(f"[Flipkart] executor error: {e}")
        products = []
    print(f"[Flipkart] {len(products)} parsed")
    return products


def parse_flipkart_json(data: dict) -> list[Product]:
    """Parse Flipkart's internal JSON API response."""
    products = []
    try:
        # Walk the JSON tree looking for product slots
        slots = []
        def find_slots(obj):
            if isinstance(obj, dict):
                if obj.get("type") in ("ORGANIC", "PRODUCT_SUMMARY"):
                    slots.append(obj)
                for v in obj.values():
                    find_slots(v)
            elif isinstance(obj, list):
                for item in obj:
                    find_slots(item)
        find_slots(data)

        for slot in slots[:6]:
            try:
                info = slot.get("value", slot)
                name = (info.get("title") or info.get("name") or "")
                price_raw = info.get("price") or info.get("sellingPrice") or info.get("currentPrice") or {}
                price = price_raw.get("value") if isinstance(price_raw, dict) else str(price_raw)
                if price:
                    price = f"₹{price:,}" if isinstance(price, int) else price
                rating = str(info.get("rating") or info.get("ratings") or "")
                image = info.get("imageUrl") or info.get("image") or ""
                url_path = info.get("url") or info.get("productUrl") or ""
                url = ("https://www.flipkart.com" + url_path) if url_path and not url_path.startswith("http") else url_path
                if name:
                    products.append(Product(name=name, price=price or None, rating=rating or None,
                                            image=image or None, url=url or None, platform="flipkart"))
            except Exception:
                continue
    except Exception as e:
        print(f"[Flipkart JSON parse] {e}")
    return products


def clean_flipkart_name(raw: str) -> str:
    """Extract clean product name from Flipkart's link text."""
    import re
    # Remove leading junk: "BestsellerAdd to Compare", "Add to Compare", etc.
    raw = re.sub(r"^(Bestseller\s*)?Add to Compare\s*", "", raw, flags=re.IGNORECASE)
    # The name is everything up to the rating pattern (digit.digit + ratings count)
    # e.g. "Apple iPhone 17 (Black, 256 GB)4.611,510 Ratings..."
    m = re.match(r"^(.+?\))\d+\.\d+", raw)
    if m:
        return m.group(1).strip()
    # Fallback: take up to first digit-heavy sequence (ratings)
    m = re.match(r"^([^0-9]{10,})", raw)
    if m:
        return m.group(1).strip()
    return raw[:120].strip()


def extract_flipkart_price(raw: str) -> str | None:
    """Extract price like ₹82,900 from Flipkart link text."""
    import re
    m = re.search(r"₹[\d,]+", raw)
    return m.group() if m else None


def extract_flipkart_rating(raw: str) -> str | None:
    """Extract rating like 4.6 from Flipkart link text."""
    import re
    # Pattern: digit.digit followed by ratings count
    m = re.search(r"(\d\.\d)\d*\s*[\d,]+\s*Ratings", raw)
    return m.group(1) if m else None


def parse_flipkart_html(html: str) -> list[Product]:
    """Parse Flipkart HTML search results (rendered by Selenium)."""
    soup = BeautifulSoup(html, "lxml")
    products = []
    seen = set()
    all_links = soup.select("a[href*='/p/']")
    print(f"[Flipkart HTML] /p/ links found: {len(all_links)}")

    for a in all_links:
        try:
            href = a.get("href", "")
            if href in seen:
                continue
            seen.add(href)
            # Clean URL — strip tracking params, keep only pid
            base = ("https://www.flipkart.com" + href) if not href.startswith("http") else href
            pid_match = re.search(r"[?]pid=([A-Z0-9]+)", base)
            full_url = f"{base.split('?')[0]}?pid={pid_match.group(1)}" if pid_match else base.split("?")[0]

            raw_text = a.get_text(strip=True)
            if len(raw_text) < 10:
                continue

            # Clean name, price, rating from the raw link text
            name = clean_flipkart_name(raw_text)
            if not name or len(name) < 5:
                continue

            price = extract_flipkart_price(raw_text)
            rating = extract_flipkart_rating(raw_text)

            # Walk up to find image (real product image, not placeholder)
            card = a
            image = None
            for _ in range(8):
                card = card.parent
                if card is None:
                    break
                for img in card.select("img"):
                    src = img.get("src", "")
                    # Skip placeholder/icon images, get real product images
                    if src and "rukminim" in src and src.startswith("https://"):
                        image = src
                        break
                if image:
                    break

            products.append(Product(name=name, price=price, rating=rating,
                                    image=image, url=full_url, platform="flipkart"))
            if len(products) >= 5:
                break
        except Exception as e:
            print(f"[Flipkart HTML] {e}")

    return products



# ── Relevance filter ──────────────────────────────────────────────────────────

def is_relevant(name: str, query: str) -> bool:
    """
    Returns True if the product name is relevant to the query.
    Strategy: all meaningful query words must appear in the product name.
    Handles common abbreviations and brand aliases.
    """
    if not name or not query:
        return False

    name_lower  = name.lower()
    query_lower = query.lower().strip()

    # Stopwords to ignore when checking relevance
    STOPWORDS = {"the","a","an","for","with","and","or","in","of","to","by","is","it","on","at","best","new","buy","price"}

    # Extract meaningful words from query
    query_words = [w for w in re.split(r"[\s\-/]+", query_lower) if len(w) > 1 and w not in STOPWORDS]

    if not query_words:
        return True  # nothing meaningful to check

    # For short 1-word queries, just check it appears in name
    if len(query_words) == 1:
        return query_words[0] in name_lower

    # For multi-word: require at least 60% of query words to match
    matched = sum(1 for w in query_words if w in name_lower)
    ratio   = matched / len(query_words)

    # Hard reject obvious mismatches: if the primary noun isn't in name
    primary = query_words[0]  # first word is usually the product type
    if primary not in name_lower and ratio < 0.5:
        return False

    return ratio >= 0.5


def filter_relevant(products: list, query: str) -> list:
    filtered = [p for p in products if is_relevant(p.name, query)]
    # If filtering removed everything, return top 3 unfiltered (better than nothing)
    return filtered if filtered else products[:3]

# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/compare", response_model=CompareResponse)
async def compare(q: str = Query(..., min_length=2, max_length=200)):
    amazon_r, flipkart_r = await asyncio.gather(
        scrape_amazon(q), scrape_flipkart(q), return_exceptions=True
    )
    if isinstance(amazon_r, Exception):
        print(f"[Amazon] Exception: {amazon_r}")
        amazon_r = []
    if isinstance(flipkart_r, Exception):
        print(f"[Flipkart] Exception: {flipkart_r}")
        flipkart_r = []

    # Filter irrelevant results (cases, accessories, wrong products)
    amazon_r   = filter_relevant(amazon_r,   q)
    flipkart_r = filter_relevant(flipkart_r, q)

    print(f"[Filter] Amazon: {len(amazon_r)} relevant | Flipkart: {len(flipkart_r)} relevant")
    return CompareResponse(query=q, amazon=amazon_r, flipkart=flipkart_r)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/debug")
async def debug(q: str = Query(...), platform: str = "amazon"):
    encoded = urllib.parse.quote_plus(q)
    url = f"https://www.amazon.in/s?k={encoded}" if platform == "amazon" else f"https://www.flipkart.com/search?q={encoded}"
    headers = amazon_headers() if platform == "amazon" else flipkart_headers()
    async with httpx.AsyncClient(headers=headers, timeout=TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url)
    soup = BeautifulSoup(resp.text, "lxml")
    cards = soup.select("div[data-component-type='s-search-result']") if platform == "amazon" else soup.select("a[href*='/p/']")
    return {"status": resp.status_code, "items_found": len(cards), "captcha": "captcha" in resp.text.lower()}