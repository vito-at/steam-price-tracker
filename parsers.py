import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse

_PRICE_NUM_RE = re.compile(r"(\d[\d\s.,]*)")


def _to_number(raw: str) -> float:
    raw = raw.strip()
    raw = raw.replace("\xa0", " ")
    raw = raw.replace(" ", "")
    if "," in raw and "." in raw:
        raw = raw.replace(",", "")
    elif "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    return float(raw)


def _find_numbers_deep(obj):
    """Recursively collect numeric-looking values from dict/list."""
    nums = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            # If value is a number already
            if isinstance(v, (int, float)):
                # Avoid tiny stuff like 0/1 flags unless it's clearly a price
                nums.append(float(v))
            else:
                nums.extend(_find_numbers_deep(v))
    elif isinstance(obj, list):
        for it in obj:
            nums.extend(_find_numbers_deep(it))
    return nums


def parse_uzum_price(html: str) -> float:
    """
    Uzum.uz pages are Next.js based. Price is usually inside <script id="__NEXT_DATA__"> JSON.
    We try BeautifulSoup first, then regex fallback.
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) BeautifulSoup way
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag and (tag.string or tag.get_text(strip=True)):
        json_text = tag.string or tag.get_text(strip=True)
        data = json.loads(json_text)
    else:
        # 2) Regex fallback (often more reliable)
        m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if not m:
            raise ValueError("Uzum: __NEXT_DATA__ not found")
        data = json.loads(m.group(1))

    # Try typical price keys
    blob = json.dumps(data, ensure_ascii=False)
    for pat in [
        r'"price"\s*:\s*(\d+)',
        r'"salePrice"\s*:\s*(\d+)',
        r'"discountPrice"\s*:\s*(\d+)',
        r'"actualPrice"\s*:\s*(\d+)',
        r'"fullPrice"\s*:\s*(\d+)',
    ]:
        mm = re.search(pat, blob)
        if mm:
            val = float(mm.group(1))
            if val > 0:
                return val

    # Fallback: numeric search
    nums = _find_numbers_deep(data)
    nums = [n for n in nums if n >= 100]
    if not nums:
        raise ValueError("Uzum: no numeric candidates found")

    nums.sort()
    top = nums[-30:] if len(nums) > 30 else nums
    top.sort()
    return top[len(top) // 2]



def parse_generic_price(html: str) -> float:
    soup = BeautifulSoup(html, "html.parser")

    for prop in ("product:price:amount", "og:price:amount"):
        tag = soup.find("meta", attrs={"property": prop})
        if tag and tag.get("content"):
            return _to_number(tag["content"])

    tag = soup.find(attrs={"itemprop": "price"})
    if tag:
        if tag.get("content"):
            return _to_number(tag["content"])
        text = tag.get_text(" ", strip=True)
        m = _PRICE_NUM_RE.search(text)
        if m:
            return _to_number(m.group(1))

    candidates = soup.select(
        "[class*='price'], [id*='price'], [data-testid*='price'], [data-test*='price']"
    )
    for el in candidates[:30]:
        text = el.get_text(" ", strip=True)
        m = _PRICE_NUM_RE.search(text)
        if m:
            try:
                val = _to_number(m.group(1))
                if val >= 1:
                    return val
            except Exception:
                pass

    text = soup.get_text(" ", strip=True)
    nums = []
    for m in _PRICE_NUM_RE.finditer(text):
        try:
            v = _to_number(m.group(1))
            if v >= 1:
                nums.append(v)
        except Exception:
            continue

    if not nums:
        raise ValueError("Could not parse price from page")

    nums.sort()
    return nums[-1]


def parse_price_for_url(url: str, html: str) -> float:
    host = (urlparse(url).netloc or "").lower()
    if "uzum.uz" in host:
        return parse_uzum_price(html)
    return parse_generic_price(html)


import os
import re
import requests

def _deep_find_price(obj):
    """Try to find a reasonable price from a JSON object."""
    if isinstance(obj, dict):
        for k in ("price", "salePrice", "discountPrice", "actualPrice", "fullPrice", "finalPrice", "sellPrice"):
            if k in obj and isinstance(obj[k], (int, float)) and obj[k] > 0:
                return float(obj[k])
        for v in obj.values():
            found = _deep_find_price(v)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for it in obj:
            found = _deep_find_price(it)
            if found is not None:
                return found
    return None


def uzum_product_id_from_url(url: str) -> str:
    # Example: ...-3-1761000?skuId=...
    m = re.search(r"-(\d+)(?:\?|$)", url)
    if not m:
        raise ValueError("Uzum: could not extract productId from URL")
    return m.group(1)


def fetch_uzum_price_via_api(url: str) -> float:
    product_id = uzum_product_id_from_url(url)

    auth = os.getenv("UZUM_AUTH_TOKEN", "").strip()
    x_iid = os.getenv("UZUM_X_IID", "").strip()
    lang = os.getenv("UZUM_LANG", "uz-UZ").strip()

    if not auth or not x_iid:
        raise ValueError("Uzum: missing UZUM_AUTH_TOKEN or UZUM_X_IID in .env")

    api_url = f"https://api.umarket.uz/api/v2/product/{product_id}"

    headers = {
        "Accept": "application/json",
        "Accept-Language": lang,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PriceTracker/1.0",
        "Authorization": f"Bearer {auth}",
        "X-Iid": x_iid,
    }

    r = requests.get(api_url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    price = _deep_find_price(data)
    if price is None:
        raise ValueError("Uzum: could not find price in API JSON")
    return price

import json
import re
from urllib.parse import urlparse

def parse_aliexpress_price(html: str) -> float:
    """
    AliExpress often embeds product state in window.runParams (JSON).
    We extract that JSON and try to find price candidates inside.
    """
    # 1) find window.runParams = {...};
    m = re.search(r'window\.runParams\s*=\s*({.*?});\s*</script>', html, re.DOTALL)
    if not m:
        # sometimes it ends without </script> in the same block
        m = re.search(r'window\.runParams\s*=\s*({.*?});', html, re.DOTALL)
    if not m:
        raise ValueError("AliExpress: window.runParams not found (page may be JS/anti-bot)")

    data = json.loads(m.group(1))

    # Common spots: runParams.data contains product/price info
    root = data.get("data", data)

    # Try common key names seen in ali state objects
    blob = json.dumps(root, ensure_ascii=False)

    # Look for typical price fields (best effort)
    for pat in [
        r'"minActivityAmount"\s*:\s*"?(\\d+\\.?\\d*)"?',
        r'"minAmount"\s*:\s*"?(\\d+\\.?\\d*)"?',
        r'"maxAmount"\s*:\s*"?(\\d+\\.?\\d*)"?',
        r'"salePrice"\s*:\s*"?(\\d+\\.?\\d*)"?',
        r'"price"\s*:\s*"?(\\d+\\.?\\d*)"?',
    ]:
        mm = re.search(pat, blob)
        if mm:
            return float(mm.group(1))

    # fallback: find first reasonable float-like number
    mm = re.search(r'(\d+\.\d+|\d+)', blob)
    if mm:
        return float(mm.group(1))

    raise ValueError("AliExpress: could not find price in runParams JSON")


def parse_price_for_url(url: str, html: str) -> float:
    host = (urlparse(url).netloc or "").lower()

    if "aliexpress." in host:
        return parse_aliexpress_price(html)

    # fallback to your existing generic parser
    return parse_generic_price(html)


import re
import requests

def _steam_price_to_float(price_text: str) -> float:
    # examples: "$1.23", "1,23€", "руб. 123,45", "123,45 pуб."
    s = price_text.strip()
    # keep digits, dot, comma
    s = re.sub(r"[^\d,\.]", "", s)
    if not s:
        raise ValueError("Steam: empty price")
    # If both separators exist, assume dot is decimal and remove commas
    if "," in s and "." in s:
        s = s.replace(",", "")
    # If only comma exists, treat it as decimal separator
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    return float(s)

def fetch_steam_priceoverview(appid: int, market_hash_name: str, currency: int = 1) -> float:
    """
    Uses Steam Community Market priceoverview endpoint.
    Returns a float price (lowest_price if available, else median_price).
    """
    url = "https://steamcommunity.com/market/priceoverview/"
    params = {
        "appid": int(appid),
        "currency": int(currency),
        "market_hash_name": market_hash_name
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PriceTracker/1.0",
        "Accept": "application/json,text/plain,*/*"
    }
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    if not data.get("success"):
        raise ValueError(f"Steam: priceoverview not successful: {data}")

    price_text = data.get("lowest_price") or data.get("median_price")
    if not price_text:
        raise ValueError(f"Steam: no price fields in response: {data}")

    return _steam_price_to_float(price_text)
