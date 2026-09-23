from datetime import datetime
from zoneinfo import ZoneInfo

from core import db
from core.config import APP_TIMEZONE
from core.phone import norm_phone
from core.statuses import validate_transition

_TZ = ZoneInfo(APP_TIMEZONE)


def _now() -> str:
    return datetime.now(_TZ).isoformat(timespec="seconds")


def _find_client(conn, phone_norm: str):
    return conn.execute(
        "SELECT id FROM clients WHERE phone_norm = ?", (phone_norm,)
    ).fetchone()


def _create_client(conn, name: str, phone_raw: str, phone_norm: str) -> int:
    cur = conn.execute(
        "INSERT INTO clients (name, phone_raw, phone_norm) VALUES (?, ?, ?)",
        (name, phone_raw, phone_norm),
    )
    return cur.lastrowid


def create_order(
    name: str,
    phone: str,
    address: str | None = None,
    items_text: str | None = None,
    amount: float = 0.0,
    prepayment: float | None = None,
    channel: str | None = None,
    tracking_number: str | None = None,
    supplier: str | None = None,
    comment: str | None = None,
) -> int:
    if not phone:
        raise ValueError("Телефон обязателен")
    if amount < 0:
        raise ValueError("amount не может быть отрицательным")
    if prepayment is None:
        prepayment = round(amount * 0.5, 2)
    if not (0 <= prepayment <= amount):
        raise ValueError("prepayment должен быть в пределах [0, amount]")

    phone_raw = phone
    phone_norm = norm_phone(phone)
    now = _now()

    with db.get_connection() as conn:
        client = _find_client(conn, phone_norm)
        if client is None:
            client_id = _create_client(conn, name, phone_raw, phone_norm)
        else:
            conn.execute(
                "UPDATE clients SET name = ?, phone_raw = ? WHERE id = ?",
                (name, phone_raw, client["id"]),
            )
            client_id = client["id"]

        cur = conn.execute(
            """INSERT INTO orders
               (client_id, address, items_text, amount, prepayment, channel,
                status, tracking_number, supplier, comment, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?, ?)""",
            (client_id, address, items_text, amount, prepayment, channel,
             tracking_number, supplier, comment, now, now),
        )
        order_id = cur.lastrowid
        conn.execute(
            """INSERT INTO status_history
               (order_id, from_status, to_status, comment, changed_at)
               VALUES (?, NULL, 'new', ?, ?)""",
            (order_id, comment, now),
        )
    return order_id


def get_order(order_id: int):
    with db.get_connection() as conn:
        row = conn.execute(
            """SELECT o.*, c.name AS client_name, c.phone_raw, c.phone_norm
               FROM orders o JOIN clients c ON c.id = o.client_id
               WHERE o.id = ?""",
            (order_id,),
        ).fetchone()
    return dict(row) if row else None


def list_orders(filters: dict | None = None) -> list[dict]:
    filters = filters or {}
    conditions = []
    params = []
    if filters.get("status"):
        conditions.append("o.status = ?")
        params.append(filters["status"])
    if filters.get("channel"):
        conditions.append("o.channel = ?")
        params.append(filters["channel"])
    if filters.get("phone_norm"):
        conditions.append("c.phone_norm = ?")
        params.append(filters["phone_norm"])
    if filters.get("date_from"):
        conditions.append("o.created_at >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        conditions.append("o.created_at <= ?")
        params.append(filters["date_to"])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""SELECT o.*, c.name AS client_name, c.phone_raw, c.phone_norm
              FROM orders o JOIN clients c ON c.id = o.client_id
              {where} ORDER BY o.created_at DESC"""
    with db.get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def change_status(order_id: int, new_status: str, comment: str | None = None):
    with db.get_connection() as conn:
        order = conn.execute(
            "SELECT id, status, amount FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if order is None:
            raise ValueError(f"Заказ {order_id} не найден")

        old_status = order["status"]
        validate_transition(old_status, new_status)

        now = _now()
        if new_status == "cancelled":
            if not comment or not comment.strip():
                raise ValueError("Для отмены заказа обязательна причина")
        if new_status == "delivered":
            conn.execute(
                "UPDATE orders SET status = ?, updated_at = ?, delivered_at = ? WHERE id = ?",
                (new_status, now, now, order_id),
            )
        elif new_status == "cancelled":
            conn.execute(
                """UPDATE orders SET status = ?, updated_at = ?, cancelled_at = ?,
                   cancel_reason = ? WHERE id = ?""",
                (new_status, now, now, comment, order_id),
            )
        else:
            conn.execute(
                "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, now, order_id),
            )
        conn.execute(
            """INSERT INTO status_history
               (order_id, from_status, to_status, comment, changed_at)
               VALUES (?, ?, ?, ?, ?)""",
            (order_id, old_status, new_status, comment, now),
        )
    return get_order(order_id)