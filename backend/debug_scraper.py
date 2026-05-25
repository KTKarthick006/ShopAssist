"""
Run: python debug_scraper.py amazon iphone
"""
import sys, asyncio, urllib.parse, httpx, random
from bs4 import BeautifulSoup

QUERY    = sys.argv[2] if len(sys.argv) > 2 else "iphone"
PLATFORM = sys.argv[1] if len(sys.argv) > 1 else "amazon"

AMAZON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.amazon.in/",
    "DNT": "1", "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Cache-Control": "max-age=0",
}

async def main():
    encoded = urllib.parse.quote_plus(QUERY)
    url = f"https://www.amazon.in/s?k={encoded}"
    print(f"\nFetching: {url}")

    async with httpx.AsyncClient(headers=AMAZON_HEADERS, timeout=20, follow_redirects=True) as client:
        await client.get("https://www.amazon.in/", timeout=10)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        resp = await client.get(url)

    print(f"Status: {resp.status_code} | Size: {len(resp.text)}")
    soup = BeautifulSoup(resp.text, "lxml")
    cards = soup.select("div[data-component-type='s-search-result']")
    print(f"Cards: {len(cards)}\n")

    for i, card in enumerate(cards[:3]):
        print(f"{'─'*60}")
        print(f"CARD {i+1}")

        # Show ALL anchor tags
        print("\nAll <a> tags:")
        for a in card.select("a"):
            href = a.get("href","")
            aria = a.get("aria-label","")
            text = a.get_text(strip=True)[:80]
            if href or aria or text:
                print(f"  href={href[:70]}")
                print(f"  aria-label={aria[:100]}")
                print(f"  text={text}")
                print()

        # Show h2
        h2 = card.select_one("h2")
        print(f"H2 outerHTML: {str(h2)[:300]}")

        # Show all spans > 15 chars
        print("\nSpans with text > 15 chars:")
        for s in card.select("span"):
            t = s.get_text(strip=True)
            cls = s.get("class", [])
            if 15 < len(t) < 250 and "price" not in " ".join(cls).lower():
                print(f"  class={cls} | '{t[:120]}'")

asyncio.run(main())