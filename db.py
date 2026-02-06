import sqlite3
from pathlib import Path
from typing import Optional, Tuple, List

DB_PATH = Path("prices.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                target_price REAL,
                notify_on_any_drop INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                price REAL NOT NULL,
                fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(item_id) REFERENCES items(id)
            )
            """
        )


def upsert_item(name: str, url: str, target_price: float, notify_on_any_drop: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO items (name, url, target_price, notify_on_any_drop)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                name=excluded.name,
                target_price=excluded.target_price,
                notify_on_any_drop=excluded.notify_on_any_drop
            """,
            (name, url, target_price, 1 if notify_on_any_drop else 0),
        )


def list_items() -> List[Tuple[int, str, str, Optional[float], int]]:
    with get_conn() as conn:
        cur = conn.execute("SELECT id, name, url, target_price, notify_on_any_drop FROM items ORDER BY id")
        return list(cur.fetchall())


def add_price(item_id: int, price: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO price_history (item_id, price) VALUES (?, ?)",
            (item_id, price),
        )


def get_last_price(item_id: int) -> Optional[float]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT price FROM price_history WHERE item_id=? ORDER BY id DESC LIMIT 1",
            (item_id,),
        )
        row = cur.fetchone()
        return float(row[0]) if row else None
