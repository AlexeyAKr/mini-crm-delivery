"""Тесты навигации (ДЕФЕКТ 1): session_state + st.switch_page.

Сквозные AppTest-сценарии менеджера: список -> карточка -> переходы.
Проверяем именно порядок «сначала кладём selected_order_id в
session_state, потом switch_page», а не query_params — на нём старые
тесты проходили, но в реальном браузере навигация не работала.

query_params оставлен фолбэком (прямые ссылки/обновление URL).
БД изолируется в tmp, заказы создаются через core.orders API — тесты
не зависят от живых данных в data/crm.sqlite.
"""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from core import db, orders

_REPO = Path(__file__).resolve().parents[1]
_ORDER_PAGE = _REPO / "pages" / "order.py"
_ORDERS_PAGE = _REPO / "pages" / "orders.py"
_NEW_ORDER_PAGE = _REPO / "pages" / "new_order.py"

_SWITCH_TARGET = "pages/order.py"


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_navigation.sqlite")
    db.init_db()
    yield


@pytest.fixture
def switch_calls(monkeypatch):
    """Перехват st.switch_page: AppTest не обязан понимать st.navigation."""
    calls = []
    monkeypatch.setattr(st, "switch_page", lambda target: calls.append(target))
    return calls


def _make_order() -> int:
    return orders.create_order(
        name="Иван",
        phone="+7 (912) 345-67-89",
        address="Москва",
        items_text="Телефон",
        amount=1200.0,
    )


def _run(page_path: Path) -> AppTest:
    at = AppTest.from_file(str(page_path), default_timeout=25)
    at.run()
    assert not at.exception, f"{page_path.name} упал: {at.exception!r}"
    return at


def _open_card_from_state(order_id: int) -> AppTest:
    at = AppTest.from_file(str(_ORDER_PAGE), default_timeout=25)
    at.session_state["selected_order_id"] = order_id
    at.run()
    assert not at.exception, f"Карточка №{order_id} упала: {at.exception!r}"
    return at


def test_card_opens_from_session_state():
    """Основной путь: selected_order_id в session_state -> карточка."""
    order_id = _make_order()
    at = _open_card_from_state(order_id)
    infos = [m.value for m in at.info]
    assert not any("Выберите заказ" in i for i in infos), f"ID не прочитан: {infos}"
    labels = [b.label for b in at.button]
    assert any("Перевести" in l or "Отменить" in l for l in labels), f"нет переходов: {labels}"


def test_card_opens_from_query_params_fallback():
    """Фолбэк: query_params всё ещё работает (прямые ссылки)."""
    order_id = _make_order()
    at = AppTest.from_file(str(_ORDER_PAGE), default_timeout=25)
    at.query_params["order_id"] = str(order_id)
    at.run()
    assert not at.exception, f"Карточка №{order_id} упала: {at.exception!r}"
    labels = [b.label for b in at.button]
    assert any("Перевести" in l or "Отменить" in l for l in labels), f"нет переходов: {labels}"


def test_card_without_id_shows_hint():
    """Нет ни session_state, ни query_params -> подсказка, без падения."""
    at = _run(_ORDER_PAGE)
    infos = [m.value for m in at.info]
    assert any("Выберите заказ в разделе «Заказы»" in i for i in infos), f"нет подсказки: {infos}"


def test_transition_keeps_session_state_on_rerun():
    """selected_order_id переживает rerun (смена статуса -> st.rerun)."""
    order_id = _make_order()
    at = _open_card_from_state(order_id)
    hits = [b for b in at.button if "Перевести в «Подтверждён»" in b.label]
    assert hits, f"нет кнопки перехода: {[b.label for b in at.button]}"
    hits[0].click().run()
    assert not at.exception, f"переход упал: {at.exception!r}"
    assert orders.get_order(order_id)["status"] == "confirmed"
    assert at.session_state["selected_order_id"] == order_id
    infos = [m.value for m in at.info]
    assert not any("Выберите заказ" in i for i in infos), f"карточка потеряла ID: {infos}"


def test_final_status_has_no_transitions():
    """Финальный статус: подсказка есть, кнопок переходов нет."""
    order_id = _make_order()
    for status in ("confirmed", "in_transit", "delivered"):
        orders.change_status(order_id, status)
    at = _open_card_from_state(order_id)
    captions = [m.value for m in at.caption]
    assert any("Финальный статус" in c for c in captions), f"нет подсказки: {captions}"
    labels = [b.label for b in at.button]
    assert not any("Перевести" in l for l in labels), f"лишние переходы: {labels}"


def test_orders_button_sets_state_then_switches(switch_calls):
    """Список: кнопка «Открыть» -> session_state ДО switch_page."""
    order_id = _make_order()
    at = _run(_ORDERS_PAGE)
    open_buttons = [b for b in at.button if b.label == "Открыть"]
    assert open_buttons, f"нет кнопок «Открыть»: {[b.label for b in at.button]}"
    open_buttons[0].click().run()
    assert not at.exception, f"клик упал: {at.exception!r}"
    assert at.session_state["selected_order_id"] == order_id
    assert switch_calls == [_SWITCH_TARGET], f"switch_page: {switch_calls}"


def test_new_order_submit_then_open_switches(switch_calls):
    """Новый заказ: submit -> pending -> кнопка «Открыть карточку» -> switch."""
    at = _run(_NEW_ORDER_PAGE)
    phone = [w for w in at.text_input if w.key == "n_phone"]
    assert phone, "нет поля телефона"
    phone[0].set_value("+7 (912) 345-67-89")
    submit = [b for b in at.button if b.label == "Сохранить"]
    assert submit, f"нет кнопки «Сохранить»: {[b.label for b in at.button]}"
    submit[0].click().run()
    assert not at.exception, f"submit упал: {at.exception!r}"

    pending_id = at.session_state["pending_order_id"]
    assert orders.get_order(pending_id) is not None

    open_buttons = [b for b in at.button if b.label == "Открыть карточку заказа"]
    assert open_buttons, f"кнопка не появилась: {[b.label for b in at.button]}"
    open_buttons[0].click().run()
    assert not at.exception, f"клик упал: {at.exception!r}"
    assert at.session_state["selected_order_id"] == pending_id
    assert "pending_order_id" not in at.session_state
    assert switch_calls == [_SWITCH_TARGET], f"switch_page: {switch_calls}"


def _fill_new_order(at: AppTest, amount: float | None = None, prepay: float | None = None) -> AppTest:
    if amount is not None:
        a = [w for w in at.number_input if w.key == "amount_input"][0]
        a.set_value(amount)
        at.run()
    if prepay is not None:
        p = [w for w in at.number_input if w.key == "prepayment_input"][0]
        p.set_value(prepay)
        at.run()
    phone = [w for w in at.text_input if w.key == "n_phone"][0]
    phone.set_value("+7 (912) 345-67-89")
    return at


def _submit_new_order(at: AppTest) -> AppTest:
    submit = [b for b in at.button if b.label == "Сохранить"][0]
    submit.click().run()
    return at


def test_new_order_auto_prepayment_50pct():
    """ДЕФЕКТ 4: сумма 2000 -> предоплата автоматически 1000."""
    at = _fill_new_order(_run(_NEW_ORDER_PAGE), amount=2000.0)
    prepay_widget = [w for w in at.number_input if w.key == "prepayment_input"][0]
    assert prepay_widget.value == 1000.0, f"преоплата не авто-подставлена: {prepay_widget.value}"

    _submit_new_order(at)
    assert not at.exception, f"submit упал: {at.exception!r}"
    order = orders.get_order(at.session_state["pending_order_id"])
    assert order["amount"] == 2000.0
    assert order["prepayment"] == 1000.0


def test_new_order_manual_prepayment_not_overwritten():
    """ДЕФЕКТ 4: ручная предоплата 700 не затирается автопересчётом."""
    at = _fill_new_order(_run(_NEW_ORDER_PAGE), amount=2000.0, prepay=700.0)
    prepay_widget = [w for w in at.number_input if w.key == "prepayment_input"][0]
    assert prepay_widget.value == 700.0

    _submit_new_order(at)
    assert not at.exception, f"submit упал: {at.exception!r}"
    order = orders.get_order(at.session_state["pending_order_id"])
    assert order["amount"] == 2000.0
    assert order["prepayment"] == 700.0


def test_new_order_prepayment_over_amount_warns_and_blocks():
    """ДЕФЕКТ 4: предоплата > сумма -> warning, кнопка «Сохранить» заблокирована."""
    at = _fill_new_order(_run(_NEW_ORDER_PAGE), amount=1000.0, prepay=1500.0)
    warnings = [m.value for m in at.warning]
    assert any("Предоплата" in w for w in warnings), f"нет warning: {warnings}"

    before = len(orders.list_orders())
    submit = [b for b in at.button if b.label == "Сохранить"][0]
    try:
        submit.click().run()
    except Exception:
        pass
    assert len(orders.list_orders()) == before, "заказ создан вопреки невалидной предоплате"
    assert "pending_order_id" not in at.session_state


def test_new_order_double_submit_no_duplicate(monkeypatch):
    """ДЕФЕКТ 5: повторный submit не создаёт дубликат."""
    real_create = orders.create_order
    calls = {"n": 0}

    def counting_create(*args, **kwargs):
        calls["n"] += 1
        return real_create(*args, **kwargs)

    monkeypatch.setattr(orders, "create_order", counting_create)

    at = _fill_new_order(_run(_NEW_ORDER_PAGE), amount=2000.0)
    _submit_new_order(at)
    assert not at.exception, f"первый submit упал: {at.exception!r}"
    assert calls["n"] == 1
    assert at.session_state["pending_order_id"]

    _submit_new_order(at)
    assert not at.exception, f"повторный submit упал: {at.exception!r}"
    assert calls["n"] == 1, f"дубликат: create_order вызван {calls['n']} раз"


def test_new_order_reset_enables_next_submission(monkeypatch, switch_calls):
    """ДЕФЕКТ 5: «Создать ещё один заказ» сбрасывает флаг для следующего заказа."""
    real_create = orders.create_order
    calls = {"n": 0}

    def counting_create(*args, **kwargs):
        calls["n"] += 1
        return real_create(*args, **kwargs)

    monkeypatch.setattr(orders, "create_order", counting_create)

    at = _fill_new_order(_run(_NEW_ORDER_PAGE), amount=2000.0)
    _submit_new_order(at)
    assert calls["n"] == 1

    reset = [b for b in at.button if b.label == "Создать ещё один заказ"]
    assert reset, f"нет кнопки сброса: {[b.label for b in at.button]}"
    reset[0].click().run()
    assert not at.exception, f"сброс упал: {at.exception!r}"
    assert at.session_state["order_submitted"] is False

    _submit_new_order(at)
    assert not at.exception, f"второй заказ упал: {at.exception!r}"
    assert calls["n"] == 2, f"ожидали 2 заказа, создано {calls['n']}"
