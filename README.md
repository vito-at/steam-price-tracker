# Steam Market Price Tracker

A lightweight Python tool that tracks prices on the **Steam Community Market** and sends **Telegram notifications** when the price drops or reaches a target value.

The project uses Steam’s public `priceoverview` API and is designed as a simple, configurable personal tool.

---

## Features

- 📉 Track Steam Community Market item prices
- 🔔 Telegram notifications on:
  - price drop
  - target price reached
- ⏱ Configurable check interval
- 💾 Price history stored locally (SQLite)
- 🧩 Clean and extendable project structure

---

## How It Works

The tracker periodically requests price data from the Steam Community Market using the official `priceoverview` endpoint.  
When a price change meets your notification conditions, a message is sent to your Telegram chat.

No HTML scraping, no browser automation — only a stable public API.

---

## Requirements

- Python **3.10+**
- A Telegram bot token
- Internet connection

---

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/your-username/steam-price-tracker.git
cd steam-price-tracker
2. Create and activate virtual environment
python -m venv .venv
Windows

.\.venv\Scripts\activate
macOS / Linux

source .venv/bin/activate
3. Install dependencies
pip install -r requirements.txt
Configuration
Environment variables
Create a .env file using the provided example:

cp .env.example .env
Fill in your values:

TG_BOT_TOKEN=your_telegram_bot_token
TG_CHAT_ID=your_chat_id
STEAM_CURRENCY=1
Steam currency codes:

1 — USD

3 — EUR

5 — RUB

23 — TRY

Config file (config.json)
Example configuration:

{
  "interval_minutes": 15,
  "items": [
    {
      "name": "AK-47 | Redline (Field-Tested)",
      "steam_appid": 730,
      "steam_market_hash_name": "AK-47 | Redline (Field-Tested)",
      "target_price": 10.0,
      "notify_on_any_drop": true
    }
  ]
}
Important:
steam_market_hash_name must exactly match the item name on Steam Market.

Running the Tracker
python main.py
The tracker will:

load configuration

fetch current prices

store price history

send Telegram notifications when conditions are met

Stop the tracker with Ctrl + C.

Project Structure
.
├── main.py
├── tracker.py
├── parsers.py
├── db.py
├── config.json
├── requirements.txt
├── .env.example
└── README.md
Known Limitations
Steam API has rate limits

Prices may vary depending on region and currency

Requires correct market_hash_name formatting
