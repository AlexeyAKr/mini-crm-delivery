import sqlite3
from pathlib import Path

from core.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    phone_raw    TEXT,
    phone_norm   TEXT,
    comment      TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL REFERENCES clients(id),
    address         TEXT,
    items_text      TEXT,
    amount          REAL DEFAULT 0,
    prepayment      REAL DEFAULT 0,
    channel         TEXT,
    status          TEXT NOT NULL DEFAULT 'new',
    tracking_number TEXT,
    supplier        TEXT,
    comment         TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivered_at    TIMESTAMP,
    cancelled_at    TIMESTAMP,
    cancel_reason   TEXT
);

CREATE TABLE IF NOT EXISTS status_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL REFERENCES orders(id),
    from_status  TEXT,
    to_status    TEXT NOT NULL,
    comment      TEXT,
    changed_by   TEXT DEFAULT 'manager',
    changed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients(phone_norm);
"""


def get_connection() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(_SCHEMA)