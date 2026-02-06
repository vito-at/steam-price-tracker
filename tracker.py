import os
import requests
from urllib.parse import urlparse
from typing import Optional, Tuple

from db import add_price, get_last_price
from parsers import parse_price_for_url, fetch_steam_priceoverview


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PriceTracker/1.0"
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def check_item(
    item_id: int,
    name: str,
    url: str,
    target_price: Optional[float],
    notify_on_any_drop: bool
) -> Tuple[float, Optional[float], bool]:

    # --- STEAM MARKET ---
    if url.startswith("steam://market/"):
        parts = url.split("/", 4)
        appid = int(parts[3])
        market_hash_name = parts[4]
        currency = int(os.getenv("STEAM_CURRENCY", "1"))

        new_price = fetch_steam_priceoverview(
            appid=appid,
            market_hash_name=market_hash_name,
            currency=currency
        )

    # --- REGULAR WEBSITES ---
    else:
        html = fetch_html(url)
        new_price = parse_price_for_url(url, html)

    last = get_last_price(item_id)
    add_price(item_id, new_price)

    should_notify = False

    if target_price is not None and new_price <= float(target_price):
        should_notify = True

    if notify_on_any_drop and last is not None and new_price < last:
        should_notify = True

    return new_price, last, should_notify
