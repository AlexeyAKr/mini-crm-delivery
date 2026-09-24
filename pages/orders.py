from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from core import db, orders
from core.config import APP_TIMEZONE
from core.phone import format_phone, norm_phone
from core.statuses import STATUS_LABELS

db.init_db()

_TZ = ZoneInfo(APP_TIMEZONE)

_CHANNELS = {
    "avito": "Авито",
    "telegram": "Телеграм",
    "manual": "Ручной ввод",
}

_HEADERS = ["ID", "Дата", "Клиент", "Телефон", "Статус", "Канал", "Сумма, ₽", ""]
_COL_WIDTHS = [1, 1.6, 2.2, 1.6, 1.4, 1.2, 1.3, 1.2]

st.title("Заказы")

period = st.radio("Период", ["Сегодня", "7 дней", "Всё время"], horizontal=True)
col1, col2, col3 = st.columns(3)
sel_statuses = col1.multiselect(
    "Статус",
    options=list(STATUS_LABELS),
    format_func=lambda s: STATUS_LABELS[s],
    placeholder="Все статусы",
)
sel_channels = col2.multiselect(
    "Канал",
    options=list(_CHANNELS),
    format_func=lambda c: _CHANNELS[c],
    placeholder="Все каналы",
)
search = col3.text_input("Поиск по телефону")

today = datetime.now(_TZ).date()
if period == "Сегодня":
    date_from = today.isoformat()
    date_to = today.isoformat()
elif period == "7 дней":
    date_from = (today - timedelta(days=6)).isoformat()
    date_to = today.isoformat()
else:
    date_from = None
    date_to = None

filters = {}
if date_from:
    filters["date_from"] = date_from
    filters["date_to"] = date_to
if sel_statuses:
    filters["statuses"] = sel_statuses
if sel_channels:
    filters["channels"] = sel_channels
if search.strip():
    filters["phone_norm"] = norm_phone(search)

rows = orders.list_orders(filters)

if not rows:
    st.info("Заказов по выбранным фильтрам не найдено")
    st.stop()

st.caption(f"Показано заказов: {len(rows)}")

cols = st.columns(_COL_WIDTHS)
for col, header in zip(cols, _HEADERS):
    col.caption(header)

for r in rows:
    cols = st.columns(_COL_WIDTHS)
    cols[0].write(str(r["id"]))
    cols[1].write((r["created_at"] or "")[:10])
    cols[2].write(r["client_name"] or "—")
    cols[3].write(format_phone(r["phone_raw"] or ""))
    cols[4].write(STATUS_LABELS.get(r["status"], r["status"]))
    cols[5].write(_CHANNELS.get(r["channel"], r["channel"]))
    cols[6].write(f"{round(r['amount'] or 0, 2):,.2f}".replace(",", " "))
    if cols[7].button("Открыть", key=f"open_order_{r['id']}"):
        st.session_state["selected_order_id"] = r["id"]
        st.switch_page("pages/order.py")