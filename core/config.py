import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _get(key: str, default: str = "") -> str:
    """Читает значение сначала из st.secrets (Streamlit Cloud),
    потом из переменных окружения / .env (локально)."""
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


APP_TIMEZONE = _get("APP_TIMEZONE", "Europe/Moscow")
GIGACHAT_CREDENTIALS = _get("GIGACHAT_CREDENTIALS", "")
GIGACHAT_SCOPE = _get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")

DB_PATH = Path(_get("DB_PATH", "data/crm.sqlite"))
if not DB_PATH.is_absolute():
    DB_PATH = BASE_DIR / DB_PATH