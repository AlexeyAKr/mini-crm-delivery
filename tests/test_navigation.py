"""Тесты ДЕФЕКТА 1 (карточка заказа: смена статусов, отмена с причиной,
история, финальный статус через st.info) и ДЕФЕКТА 5 (flash после сохранения).

Сквозные AppTest-сценарии менеджера: список -> карточка -> переходы.
БД изолируется в tmp, заказы создаются через core.orders API — тесты
не зависят от живых данных в data/orders.sqlite.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import db, orders
from core.flash import set_message

_REPO = Path(__file__).resolve().parents[1]
_PAGE = _REPO / "pages" / "order.py"

_STATUSES = ("confirmed", "in_transit", "delivered")


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_navigation.sqlite")
    db.init_db()
    yield


def _make_order(id_prefix: str = "") -> int:
    """Создать заказ и привести его в нужный статус через API."""
    order_id = orders.create_order(
        name="Иван",
        phone="+7 (912) 345-67-89",
        address="Москва",
        items_text="Телефон",
        amount=1200.0,
    )
    return order_id


def _make_order_in(status: str) -> int:
    """Создать заказ, довести его до нужного статуса цепочкой переходов."""
    order_id = _make_order()
    chain = ["confirmed", "in_transit", "delivered"]
    target_idx = chain.index(status)
    for step in chain[:target_idx + 1]:
        orders.change_status(order_id, step)
    return order_id


def _open_card(order_id: int) -> AppTest:
    at = AppTest.from_file(str(_PAGE), default_timeout=25)
    at.query_params["order_id"] = str(order_id)
    at.run()
    assert not at.exception, f"Карточка №{order_id} упала: {at.exception!r}"
    return at


def test_order_card_opens_and_renders_transitions():
    """ДЕФЕКТ 1: карточка открывается, кнопки переходов видны."""
    order_id = _make_order()
    at = _open_card(order_id)
    labels = [b.label for b in at.button]
    assert any("Перевести" in l or "Отменить" in l for l in labels), f"Нет переходов: {labels}"


def test_transition_new_to_confirmed_fires_flash():
    """ДЕФЕКТ 1+5: new->confirmed обновляет статус, flash переживает rerun."""
    order_id = _make_order()
    at = _open_card(order_id)
    hits = [b for b in at.button if "Перевести в «Подтверждён»" in b.label]
    assert hits, f"Нет кнопки «Перевести в Подтверждён»: {[b.label for b in at.button]}"
    hits[0].click().run()
    assert not at.exception, f"Переход упал: {at.exception!r}"
    flashes = [m.value for m in at.success] + [m.value for m in at.info]
    assert any("Статус обновлён" in f for f in flashes), f"flash не виден: {flashes}"


def test_final_status_rendered_as_info():
    """ДЕФЕКТ 1: финальный статус по ТЗ — st.info, а не st.caption."""
    order_id = _make_order_in("delivered")
    at = _open_card(order_id)
    infos = [m.value for m in at.info]
    assert any("Финальный статус" in i for i in infos), f"info не найден: {infos}"
