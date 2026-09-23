from datetime import date, datetime
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

    statuses = filters.get("statuses")
    if not statuses and filters.get("status"):
        statuses = [filters["status"]]
    if statuses:
        conditions.append(
            "o.status IN (" + ", ".join(["?"] * len(statuses)) + ")"
        )
        params.extend(statuses)

    channels = filters.get("channels")
    if not channels and filters.get("channel"):
        channels = [filters["channel"]]
    if channels:
        conditions.append(
            "o.channel IN (" + ", ".join(["?"] * len(channels)) + ")"
        )
        params.extend(channels)

    if filters.get("phone_norm"):
        conditions.append("c.phone_norm = ?")
        params.append(filters["phone_norm"])
    if filters.get("date_from"):
        conditions.append("substr(o.created_at, 1, 10) >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        conditions.append("substr(o.created_at, 1, 10) <= ?")
        params.append(filters["date_to"])

    sql = (
        "SELECT o.*, c.name AS client_name, c.phone_raw, c.phone_norm "
        "FROM orders o JOIN clients c ON c.id = o.client_id "
    )
    if conditions:
        sql += "WHERE " + " AND ".join(conditions) + " "
    sql += "ORDER BY o.created_at DESC"
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


_EDITABLE_FIELDS = (
    "address",
    "items_text",
    "amount",
    "prepayment",
    "channel",
    "tracking_number",
    "supplier",
    "comment",
)

_EDITABLE_SET_CLAUSES = {
    "address": "address = ?",
    "items_text": "items_text = ?",
    "amount": "amount = ?",
    "prepayment": "prepayment = ?",
    "channel": "channel = ?",
    "tracking_number": "tracking_number = ?",
    "supplier": "supplier = ?",
    "comment": "comment = ?",
}


def update_order(
    order_id: int,
    phone: str | None = None,
    name: str | None = None,
    address: str | None = None,
    items_text: str | None = None,
    amount: float | None = None,
    prepayment: float | None = None,
    channel: str | None = None,
    tracking_number: str | None = None,
    supplier: str | None = None,
    comment: str | None = None,
):
    updates = {}
    for field in _EDITABLE_FIELDS:
        value = locals()[field]
        if value is not None:
            updates[field] = value

    now = _now()
    with db.get_connection() as conn:
        order = conn.execute(
            "SELECT id, client_id, amount FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if order is None:
            raise ValueError(f"Заказ {order_id} не найден")

        if "amount" in updates and updates["amount"] < 0:
            raise ValueError("amount не может быть отрицательным")
        if "prepayment" in updates:
            effective_amount = updates.get("amount", order["amount"])
            if not (0 <= updates["prepayment"] <= effective_amount):
                raise ValueError("prepayment должен быть в пределах [0, amount]")

        if updates:
            set_clause = ", ".join(_EDITABLE_SET_CLAUSES[f] for f in updates)
            values = [updates[f] for f in updates]
            conn.execute(
                f"UPDATE orders SET {set_clause}, updated_at = ? WHERE id = ?",
                [*values, now, order_id],
            )

        if phone is not None or name is not None:
            phone_raw = phone if phone is not None else None
            phone_norm = norm_phone(phone) if phone is not None else None
            client = conn.execute(
                "SELECT id, name, phone_raw, phone_norm FROM clients WHERE id = ?",
                (order["client_id"],),
            ).fetchone()
            new_raw = phone_raw if phone_raw is not None else client["phone_raw"]
            new_norm = phone_norm if phone_norm is not None else client["phone_norm"]
            new_name = name if name is not None else client["name"]
            conn.execute(
                "UPDATE clients SET name = ?, phone_raw = ?, phone_norm = ? WHERE id = ?",
                (new_name, new_raw, new_norm, order["client_id"]),
            )
    return get_order(order_id)


def get_status_history(order_id: int) -> list[dict]:
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM status_history WHERE order_id = ? ORDER BY id DESC",
            (order_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def daily_summary(day: date | None = None) -> dict:
    if day is None:
        day = datetime.now(_TZ).date()
    day_key = day.isoformat()
    with db.get_connection() as conn:
        row = conn.execute(
            """SELECT COUNT(*)                              AS orders,
                      COALESCE(SUM(CASE WHEN status <> 'cancelled'
                                        THEN amount ELSE 0 END), 0) AS amount,
                      COALESCE(SUM(CASE WHEN status = 'delivered'
                                        THEN 1 ELSE 0 END), 0)      AS delivered,
                      COALESCE(SUM(CASE WHEN status = 'cancelled'
                                        THEN 1 ELSE 0 END), 0)      AS cancelled
               FROM orders
               WHERE substr(created_at, 1, 10) = ?""",
            (day_key,),
        ).fetchone()
    return dict(row)