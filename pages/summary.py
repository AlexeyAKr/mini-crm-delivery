from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from core import db, orders
from core.config import APP_TIMEZONE

db.init_db()

_TZ = ZoneInfo(APP_TIMEZONE)

st.title("Сводка дня")

day = st.date_input("Дата", value=datetime.now(_TZ).date())
summary = orders.daily_summary(day)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Заказов", summary["orders"])
col2.metric("Сумма", f"{summary['amount']:,.2f} ₽")
col3.metric("Доставлено", summary["delivered"])
col4.metric("Отменено", summary["cancelled"])

st.caption("Сумма — без отменённых заказов. Отменённые показаны отдельно.")