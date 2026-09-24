import streamlit as st

from core import db, orders
from core.phone import format_phone
from core.statuses import ALLOWED_TRANSITIONS, STATUS_LABELS

db.init_db()

_CHANNELS = {
    "avito": "Авито",
    "telegram": "Телеграм",
    "manual": "Ручной ввод",
}

_FIELDS = [
    ("client_name", "Имя"),
    ("phone", "Телефон"),
    ("address", "Адрес"),
    ("items_text", "Состав заказа"),
    ("amount", "Сумма"),
    ("prepayment", "Предоплата"),
    ("channel", "Канал"),
    ("tracking_number", "Трек-номер"),
    ("supplier", "Поставщик"),
    ("comment", "Комментарий"),
    ("created_at", "Создан"),
]


def _apply_transition(order_id: int, target: str, comment: str | None) -> None:
    try:
        orders.change_status(order_id, target, comment)
    except ValueError as exc:
        st.error(str(exc))
    else:
        st.success("Статус обновлён")
        st.rerun()

st.title("Карточка заказа")

raw_id = st.session_state.get("selected_order_id") or st.query_params.get("order_id")
if not raw_id:
    st.info("Выберите заказ в разделе «Заказы»")
    st.stop()
try:
    order_id = int(raw_id)
except (TypeError, ValueError):
    st.error("Некорректный ID заказа")
    st.stop()

order = orders.get_order(order_id)
if order is None:
    st.error(f"Заказ №{order_id} не найден")
    st.stop()

st.subheader(f"Заказ №{order_id}")

for key, label in _FIELDS:
    if key == "phone":
        value = format_phone(order.get("phone_raw") or "")
    elif key in ("amount", "prepayment"):
        value = f"{round(order.get(key) or 0, 2):,.2f} ₽".replace(",", " ")
    elif key == "channel":
        value = _CHANNELS.get(order.get("channel"), order.get("channel"))
    elif key == "created_at":
        value = (order.get("created_at") or "")[:10]
    else:
        value = order.get(key)
    st.write(f"**{label}:** {value if value not in (None, '') else '—'}")

current = order["status"]
st.divider()
st.write(f"**Текущий статус:** {STATUS_LABELS.get(current, current)}")

allowed = ALLOWED_TRANSITIONS.get(current, [])
if not allowed:
    st.caption("Финальный статус — дальнейшие переходы недоступны.")

for target in allowed:
    if target == "cancelled":
        reason = st.text_input("Причина отмены *")
        if st.button("Отменить заказ", disabled=not reason.strip()):
            _apply_transition(order_id, target, reason)
    else:
        if st.button(f"Перевести в «{STATUS_LABELS.get(target, target)}»"):
            _apply_transition(order_id, target, None)

st.divider()
with st.expander("✏️ Редактировать"):
    with st.form("edit_order_form"):
        f_name = st.text_input("Имя клиента", value=order.get("client_name") or "")
        f_phone = st.text_input("Телефон", value=order.get("phone_raw") or "")
        f_address = st.text_area("Адрес", value=order.get("address") or "")
        f_items = st.text_area("Состав заказа", value=order.get("items_text") or "")
        f_amount = st.number_input("Сумма, ₽", min_value=0.0, step=100.0,
                                   value=float(order.get("amount") or 0))
        f_prepayment = st.number_input(
            "Предоплата, ₽", min_value=0.0, max_value=f_amount, step=50.0,
            value=float(order.get("prepayment") or 0),
        )
        f_channel_index = (
            list(_CHANNELS).index(order.get("channel"))
            if order.get("channel") in _CHANNELS else 0
        )
        f_channel = st.selectbox(
            "Канал", options=list(_CHANNELS),
            format_func=lambda c: _CHANNELS[c],
            index=f_channel_index,
        )
        f_tracking = st.text_input("Трек-номер", value=order.get("tracking_number") or "")
        f_supplier = st.text_input("Поставщик", value=order.get("supplier") or "")
        f_comment = st.text_area("Комментарий", value=order.get("comment") or "")
        saved = st.form_submit_button("💾 Сохранить")
    if saved:
        try:
            orders.update_order(
                order_id,
                name=f_name,
                phone=f_phone,
                address=f_address,
                items_text=f_items,
                amount=f_amount,
                prepayment=f_prepayment,
                channel=f_channel,
                tracking_number=f_tracking,
                supplier=f_supplier,
                comment=f_comment,
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success("Изменения сохранены")
            st.rerun()

st.divider()
st.subheader("История")
history = orders.get_status_history(order_id)
if not history:
    st.caption("Записей нет")
for h in history:
    from_label = STATUS_LABELS.get(h["from_status"], h["from_status"] or "—")
    to_label = STATUS_LABELS.get(h["to_status"], h["to_status"])
    st.write(
        f"- {(h['changed_at'] or '')[:16]} · {from_label} → {to_label}"
        + (f" · _{h['comment']}_" if h["comment"] else "")
    )