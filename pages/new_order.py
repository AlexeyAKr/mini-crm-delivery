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


def _recalc_prepay() -> None:
    if not st.session_state.get("prepayment_touched"):
        st.session_state["prepayment_input"] = round(
            st.session_state["amount_input"] * 0.5, 2
        )


def _mark_prepay_touched() -> None:
    st.session_state["prepayment_touched"] = True


def _reset_new_order() -> None:
    st.session_state["order_submitted"] = False
    st.session_state["prepayment_touched"] = False
    st.session_state["prepayment_input"] = round(
        st.session_state["amount_input"] * 0.5, 2
    )


def _update_form_state(parsed: dict) -> None:
    for src, dst in _TEXT_PRELOAD:
        if parsed.get(src):
            st.session_state[dst] = str(parsed[src])
    if parsed.get("amount"):
        amount = float(parsed["amount"])
        st.session_state["amount_input"] = amount
        st.session_state["prepayment_input"] = round(amount * 0.5, 2)
        st.session_state["prepayment_touched"] = False
    if parsed.get("channel") in _CHANNELS:
        st.session_state["n_channel"] = parsed["channel"]


st.title("Новый заказ")

if "order_submitted" not in st.session_state:
    st.session_state["order_submitted"] = False
if "amount_input" not in st.session_state:
    st.session_state["amount_input"] = 0.0
if "prepayment_input" not in st.session_state:
    st.session_state["prepayment_input"] = 0.0
if "prepayment_touched" not in st.session_state:
    st.session_state["prepayment_touched"] = False

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

col1, col2 = st.columns(2)
amount = col1.number_input(
    "Сумма, ₽",
    min_value=0.0,
    step=100.0,
    key="amount_input",
    on_change=_recalc_prepay,
)
prepayment = col2.number_input(
    "Предоплата, ₽",
    min_value=0.0,
    step=50.0,
    key="prepayment_input",
    on_change=_mark_prepay_touched,
)

prepay_valid = (
    0 <= st.session_state["prepayment_input"]
    <= st.session_state["amount_input"]
)
if not prepay_valid:
    st.warning("Предоплата не может превышать сумму заказа")

st.divider()

with st.form("new_order_form"):
    name = st.text_input("Имя клиента", key="n_name")
    phone = st.text_input("Телефон *", key="n_phone")
    address = st.text_area("Адрес", key="n_address")
    items_text = st.text_area("Состав заказа", key="n_items")
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
    submitted = st.form_submit_button(
        "Сохранить", type="primary", disabled=not prepay_valid
    )

if submitted:
    if st.session_state["order_submitted"]:
        st.warning("Заказ уже сохранён — начните новый заказ")
    else:
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
            st.session_state["order_submitted"] = True
            st.session_state["pending_order_id"] = order_id

if st.session_state.get("pending_order_id"):
    col_open, col_new = st.columns(2)
    if col_open.button("Открыть карточку заказа", key="open_pending_card"):
        st.session_state["selected_order_id"] = int(
            st.session_state.pop("pending_order_id")
        )
        st.session_state["order_submitted"] = False
        st.switch_page("pages/order.py")
    if col_new.button(
        "Создать ещё один заказ", key="reset_new_order", on_click=_reset_new_order
    ):
        pass