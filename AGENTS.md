# AGENTS.md — Mini-CRM ChinaGoods

## Роль
Напарник по разработке Mini-CRM доставки для ChinaGoods.
Стек: Python 3.11+, Streamlit, SQLite, GigaChat API.
ОС: Windows + PowerShell. Редактор: VS Code + OpenCode.

## Источник правды
- SPEC.md — требования. Читай перед любой задачей.
- AGENTS.md (этот файл) — правила.
- Если задача противоречит SPEC.md — сначала спроси, потом делай.

## Стиль работы
1. Сначала план, потом код. Задача > 15 строк — сначала план в 3–7 шагов, дождись подтверждения.
2. Один шаг — один коммит.
3. Не трогай .env. Никогда не коммить, не печатать в логах, не выводить в UI.
4. Маленькие функции. ≤ 40 строк, одна ответственность.
5. Тесты — на статусы и телефон. Остальное — по желанию.
6. Русские подписи в UI, английские имена в коде и БД.
7. Никаких магических строк — константы в config.py или в начале модуля.

## Структура проекта (не менять без согласования)

mini-crm-delivery/
├── app.py
├── pages/
│   ├── orders.py
│   ├── order.py
│   ├── new_order.py
│   └── summary.py
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── statuses.py
│   ├── orders.py
│   ├── phone.py
│   └── ai_parser.py
├── tests/
│   ├── __init__.py
│   ├── test_statuses.py
│   ├── test_phone.py
│   └── test_orders.py
├── data/
│   └── .gitkeep
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── README.md
├── SPEC.md
└── AGENTS.md

## Разделение ответственности (важно!)

- core/statuses.py — только чистая логика, без импорта db.py:
  - ALLOWED_TRANSITIONS
  - STATUS_LABELS
  - can_transition(from_status: str, to_status: str) -> bool
  - validate_transition(from_status: str, to_status: str) -> None (raise ValueError)

- core/orders.py — сервисный слой, работает с БД:
  - create_order(...)
  - get_order(order_id)
  - list_orders(filters...)
  - change_status(order_id, new_status, comment=None) — вызывает validate_transition, обновляет orders, пишет в status_history.

## Статусы — жёсткие правила

- Единственный источник истины — ALLOWED_TRANSITIONS в core/statuses.py.
- Смена — только через change_status() из core/orders.py.
- Недопустимый переход → ValueError.
- Каждая смена → запись в status_history с changed_at = now().
- cancelled требует непустой comment (причина).
- delivered проставляет delivered_at.

## Работа с БД

- SQLite, файл data/crm.sqlite.
- Папка data/ в репозитории (через data/.gitkeep), файл *.sqlite — в .gitignore.
- В core/db.py:get_connection() — Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
  до sqlite3.connect(). Иначе деплой на Streamlit Cloud упадёт на первом запуске.
- Схема — core/db.py:init_db() (CREATE TABLE IF NOT EXISTS + индексы).
- Все запросы — параметризованные (?), никаких f-строк в SQL.
- Деньги — REAL, округление до 2 знаков при выводе.
- Даты — TIMESTAMP, локальное время (Europe/Moscow).

## Безопасность

- .gitignore создаётся ДО git init.
- .env в .gitignore с первого коммита.
- .env.example — только плейсхолдеры.
- Никаких ключей в промптах, скриншотах, README, коммитах.
- Для тестов — фиктивные ключи.
- Переменная ключа GigaChat — строго GIGACHAT_CREDENTIALS (не GIGACHAT_KEY).
  Имя совпадает с документацией GigaChat и с проектом ВК-бота ChinaGoods,
  код парсера оттуда переносится без правок.

## Тестирование

- pytest tests/ -v перед каждым «готово».
- Обязательные тесты:
  - все допустимые переходы;
  - запрещённые (перескок, откат, смена из delivered/cancelled);
  - norm_phone на +7, 8, пробелы, скобки, дефисы;
  - создание → смена → delivered_at;
  - сводка не считает cancelled.

## Формат ответа

- В конце: что сделано, как проверить, что дальше.
- Не пиши «всё готово», если тесты не запускались.

## Запрещено

- Добавлять ИИ «для галочки».
- Коммитить data/*.sqlite, .env, __pycache__, .venv.
- Переписывать функции без предупреждения.
- Использовать print() для логов — только logging или st.write.
- Импортировать db в statuses.py (нарушает разделение).
