from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from core import db, orders
from core.config import APP_TIMEZONE

_TZ = ZoneInfo(APP_TIMEZONE)


def _today_key():
    return datetime.now(_TZ).date()


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite")
    db.init_db()
    yield


def _create(amount=1000.0, **kwargs):
    return orders.create_order(name="Иван", phone="+7 (912) 345-67-89", amount=amount, **kwargs)


def test_full_flow_to_delivered():
    order_id = _create()
    for status in ("confirmed", "in_transit", "delivered"):
        orders.change_status(order_id, status)
    order = orders.get_order(order_id)
    assert order["status"] == "delivered"
    assert order["delivered_at"] is not None


def test_delivered_at_timestamp_only_after_delivered():
    order_id = _create()
    orders.change_status(order_id, "confirmed")
    order = orders.get_order(order_id)
    assert order["delivered_at"] is None
    orders.change_status(order_id, "in_transit")
    orders.change_status(order_id, "delivered")
    assert orders.get_order(order_id)["delivered_at"] is not None


def test_jump_new_to_in_transit_forbidden():
    order_id = _create()
    with pytest.raises(ValueError):
        orders.change_status(order_id, "in_transit")


def test_rollback_from_delivered_forbidden():
    order_id = _create()
    for status in ("confirmed", "in_transit", "delivered"):
        orders.change_status(order_id, status)
    with pytest.raises(ValueError):
        orders.change_status(order_id, "in_transit")


def test_change_from_cancelled_forbidden():
    order_id = _create()
    orders.change_status(order_id, "cancelled", comment="Клиент передумал")
    with pytest.raises(ValueError):
        orders.change_status(order_id, "confirmed")


def test_cancelled_requires_comment():
    order_id = _create()
    with pytest.raises(ValueError):
        orders.change_status(order_id, "cancelled")
    with pytest.raises(ValueError):
        orders.change_status(order_id, "cancelled", comment="   ")


def test_cancelled_with_comment_sets_cancelled_at():
    order_id = _create()
    orders.change_status(order_id, "cancelled", comment="Нет товара на складе")
    order = orders.get_order(order_id)
    assert order["status"] == "cancelled"
    assert order["cancelled_at"] is not None
    assert order["cancel_reason"] == "Нет товара на складе"


def test_status_history_records_each_change():
    order_id = _create()
    orders.change_status(order_id, "confirmed")
    orders.change_status(order_id, "cancelled", comment="Передумал")
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT from_status, to_status FROM status_history WHERE order_id = ? ORDER BY id",
            (order_id,),
        ).fetchall()
    assert [(r["from_status"], r["to_status"]) for r in rows] == [
        (None, "new"),
        ("new", "confirmed"),
        ("confirmed", "cancelled"),
    ]


def test_update_order_edits_fields_and_normalizes_phone():
    order_id = _create(amount=1000.0)
    orders.update_order(
        order_id, address="ул. Мира 2", amount=2000.0, prepayment=0.0
    )
    order = orders.get_order(order_id)
    assert order["address"] == "ул. Мира 2"
    assert order["amount"] == 2000.0
    assert order["prepayment"] == 0.0

    orders.update_order(order_id, phone="8 (903) 111-22-33")
    order = orders.get_order(order_id)
    assert order["phone_raw"] == "8 (903) 111-22-33"
    assert order["phone_norm"] == "9031112233"


def test_update_order_prepayment_bounds():
    order_id = _create(amount=1000.0)
    with pytest.raises(ValueError):
        orders.update_order(order_id, amount=500.0, prepayment=600.0)


def test_list_orders_multiselect_and_phone_filter():
    order_id = _create(amount=100.0)
    orders.change_status(order_id, "cancelled", comment="Передумал")

    rows = orders.list_orders({"statuses": ["new", "delivered"]})
    assert all(r["status"] in ("new", "delivered") for r in rows)

    rows = orders.list_orders({"statuses": ["cancelled"]})
    assert [r["id"] for r in rows] == [order_id]


def test_daily_summary_excludes_cancelled_amount():
    _create(amount=1000.0)
    cancelled_id = _create(amount=500.0)
    orders.change_status(cancelled_id, "cancelled", comment="Передумал")

    delivered_id = _create(amount=700.0)
    for status in ("confirmed", "in_transit", "delivered"):
        orders.change_status(delivered_id, status)

    summary = orders.daily_summary(_today_key())
    assert summary["orders"] == 3
    assert summary["amount"] == 1700.0
    assert summary["delivered"] == 1
    assert summary["cancelled"] == 1