import streamlit as st

from core import db, orders
from core.ai_parser import GigaChatUnavailableError, parse_request

db.init_db()

_CHANNELS = {
    "avito": "Авито",
    "telegram": "Телеграм",
    "manual": "Ручной ввод",
}

_TEXT_PRELOAD = [
    ("name", "n_name"),
    ("phone", "n_phone"),
    ("address", "n_address"),
    ("items", "n_items"),
]


def _update_form_state(parsed: dict) -> None:
    for src, dst in _TEXT_PRELOAD:
        if parsed.get(src):
            st.session_state[dst] = str(parsed[src])
    if parsed.get("amount"):
        st.session_state["n_amount"] = float(parsed["amount"])
    if parsed.get("channel") in _CHANNELS:
        st.session_state["n_channel"] = parsed["channel"]

st.title("Новый заказ")

ai_text = st.text_area("Вставить текст заявки (автозаполнение через ИИ)")
if st.button("Разобрать с ИИ"):
    try:
        parsed = parse_request(ai_text)
    except GigaChatUnavailableError:
        st.error("GigaChat недоступен — заполните вручную")
    else:
        if parsed:
            _update_form_state(parsed)
            st.rerun()
        else:
            st.warning("Не удалось разобрать текст — заполните вручную")

st.divider()

with st.form("new_order_form"):
    name = st.text_input("Имя клиента", key="n_name")
    phone = st.text_input("Телефон *", key="n_phone")
    address = st.text_area("Адрес", key="n_address")
    items_text = st.text_area("Состав заказа", key="n_items")
    col1, col2 = st.columns(2)
    amount = col1.number_input("Сумма, ₽", min_value=0.0, step=100.0, key="n_amount")
    prepayment = col2.number_input(
        "Предоплата, ₽",
        min_value=0.0,
        max_value=amount,
        value=round(amount * 0.5, 2),
        step=50.0,
        key="n_prepayment",
    )
    channel = st.selectbox(
        "Канал заявки",
        options=list(_CHANNELS),
        format_func=lambda c: _CHANNELS[c],
        key="n_channel",
    )
    col3, col4 = st.columns(2)
    tracking_number = col3.text_input("Трек-номер", key="n_tracking")
    supplier = col4.text_input("Поставщик", key="n_supplier")
    comment = st.text_area("Комментарий", key="n_comment")
    submitted = st.form_submit_button("Сохранить", type="primary")

if submitted:
    try:
        order_id = orders.create_order(
            name=name,
            phone=phone,
            address=address,
            items_text=items_text,
            amount=amount,
            prepayment=prepayment,
            channel=channel,
            tracking_number=tracking_number,
            supplier=supplier,
            comment=comment,
        )
    except ValueError as exc:
        st.error(str(exc))
    else:
        st.success(f"Заказ №{order_id} создан")
        if st.button("Открыть карточку заказа"):
            st.query_params["order_id"] = str(order_id)
            st.switch_page("pages/order.py")