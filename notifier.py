import os
import requests


class TelegramNotifier:
    def __init__(self) -> None:
        self.token = os.getenv("TG_BOT_TOKEN")
        self.chat_id = os.getenv("TG_CHAT_ID")

    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str) -> None:
        if not self.enabled():
            # молча не шлём, но можно логировать
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        resp = requests.post(url, json={"chat_id": self.chat_id, "text": text}, timeout=20)
        resp.raise_for_status()
