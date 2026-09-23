import streamlit as st

st.set_page_config(page_title="Mini-CRM ChinaGoods", page_icon="📦", layout="wide")

pg = st.navigation([
    st.Page("pages/orders.py", title="Заказы", icon="📦"),
    st.Page("pages/order.py", title="Карточка", icon="📋"),
    st.Page("pages/new_order.py", title="Новый заказ", icon="➕"),
    st.Page("pages/summary.py", title="Сводка дня", icon="📊"),
])
pg.run()