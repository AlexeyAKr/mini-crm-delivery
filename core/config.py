import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Moscow")
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS", "")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")

DB_PATH = Path(os.getenv("DB_PATH", "data/crm.sqlite"))
if not DB_PATH.is_absolute():
    DB_PATH = BASE_DIR / DB_PATH