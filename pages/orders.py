from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
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

_COLUMNS = ["ID", "Дата", "Клиент", "Телефон", "Статус", "Канал", "Сумма, ₽"]

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

data = []
for r in rows:
    data.append([
        r["id"],
        (r["created_at"] or "")[:10],
        r["client_name"],
        format_phone(r["phone_raw"] or ""),
        STATUS_LABELS.get(r["status"], r["status"]),
        _CHANNELS.get(r["channel"], r["channel"]),
        round(r["amount"] or 0, 2),
    ])
df = pd.DataFrame(data, columns=_COLUMNS)

event = st.dataframe(df, hide_index=True, width="stretch",
                     on_select="rerun", selection_mode="single-row")
if event.selection.rows:
    row = df.iloc[event.selection.rows[0]]
    st.query_params["order_id"] = str(row["ID"])
    st.switch_page("pages/order.py")

st.caption(f"Показано заказов: {len(rows)}")