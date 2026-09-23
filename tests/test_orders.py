import pytest

from core import db, orders


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