import json
import time
from pathlib import Path

from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from db import init_db, upsert_item, list_items
from tracker import check_item
from notifier import TelegramNotifier


CONFIG_PATH = Path("config.json")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError("config.json not found")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def sync_items_from_config(cfg: dict) -> None:
    for it in cfg.get("items", []):
        # Steam item
        if "steam_appid" in it and "steam_market_hash_name" in it:
            url = f"steam://market/{it['steam_appid']}/{it['steam_market_hash_name']}"
            upsert_item(
                name=it["name"],
                url=url,
                target_price=float(it.get("target_price")) if it.get("target_price") is not None else None,
                notify_on_any_drop=bool(it.get("notify_on_any_drop", False)),
            )
        else:
            # Generic web item (old style)
            upsert_item(
                name=it["name"],
                url=it["url"],
                target_price=float(it.get("target_price")) if it.get("target_price") is not None else None,
                notify_on_any_drop=bool(it.get("notify_on_any_drop", False)),
            )



def run_check(notifier: TelegramNotifier, currency: str) -> None:
    items = list_items()
    for item_id, name, url, target_price, notify_on_any_drop in items:
        try:
            new_price, last_price, should_notify = check_item(
                item_id=item_id,
                name=name,
                url=url,
                target_price=target_price,
                notify_on_any_drop=bool(notify_on_any_drop),
            )

            if should_notify:
                lp = f"{last_price:.0f}" if last_price is not None else "N/A"
                tp = f"{target_price:.0f}" if target_price is not None else "N/A"
                text = (
                    f"📉 Price alert!\n"
                    f"{name}\n"
                    f"Now: {new_price:.0f} {currency}\n"
                    f"Prev: {lp} {currency}\n"
                    f"Target: {tp} {currency}\n"
                    f"{url}"
                )
                notifier.send(text)

            print(f"[OK] {name}: {new_price:.0f} {currency}")

        except Exception as e:
            print(f"[ERR] {name} -> {e}")


def main():
    load_dotenv()
    init_db()

    cfg = load_config()
    sync_items_from_config(cfg)

    interval = int(cfg.get("interval_minutes", 30))
    currency = cfg.get("currency", "USD")

    notifier = TelegramNotifier()
    if notifier.enabled():
        print("Telegram notifications: enabled")
    else:
        print("Telegram notifications: disabled (set TG_BOT_TOKEN and TG_CHAT_ID in .env)")

    sched = BackgroundScheduler()
    sched.add_job(run_check, "interval", minutes=interval, args=[notifier, currency], next_run_time=None)
    sched.start()

    # First run immediately
    run_check(notifier, currency)

    print(f"Running. Check interval: {interval} minutes. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        sched.shutdown()


if __name__ == "__main__":
    main()
