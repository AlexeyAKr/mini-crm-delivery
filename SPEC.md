# SPEC.md — Mini-CRM доставки ChinaGoods

## 1. Проблема и пользователь

**Пользователь:** менеджер ChinaGoods (один человек — владелец).
**Проблема:** заявки приходят из Авито, Telegram и вручную. Теряются, статус помнится «в голове».
Нет сводки: сколько заказов, на какую сумму, сколько доставлено.
**Что изменит:** единый список заказов со статусами, поиск по телефону, фильтры по дню и статусу, сводка дня.

## 2. Пользователи и роли

- **Менеджер** — создаёт, редактирует заказы, меняет статусы, смотрит сводку.
- Авторизация в MVP: без логинов (один пользователь).

## 3. Статусная модель (4 + отмена)

new → confirmed → in_transit → delivered

cancelled — из любого, кроме delivered

ALLOWED_TRANSITIONS = {
    "new":         ["confirmed", "cancelled"],
    "confirmed":   ["in_transit", "cancelled"],
    "in_transit":  ["delivered", "cancelled"],
    "delivered":   [],
    "cancelled":   [],
}

STATUS_LABELS = {
    "new":         "Новый",
    "confirmed":   "Подтверждён",
    "in_transit":  "В пути",
    "delivered":   "Доставлен",
    "cancelled":   "Отменён",
}

Запрещено: перескоки, откаты, смена из delivered или cancelled.

## 4. Каналы заявок

- avito — основной
- telegram — второй
- manual — ручной ввод (звонок, WhatsApp, офлайн)

## 5. Главный сценарий (демо)

1. Менеджер открывает «Заказы».
2. Жмёт «+ Новый заказ».
3. Вставляет текст заявки → GigaChat предзаполняет поля → менеджер проверяет.
4. Сохраняет → заказ в списке со статусом «Новый».
5. Открывает карточку, переводит: Подтверждён → В пути → Доставлен.
6. Возвращается, ищет по телефону — находит.
7. Фильтр «сегодня + доставлен» — видит только доставленные сегодня.
8. Открывает «Сводка дня» — видит цифры.

Критерий: сценарий проходится без объяснений за ≤ 2 минуты.

## 6. Экраны (Streamlit)

| Экран | Файл | Что на нём |
|---|---|---|
| Список заказов | pages/orders.py | Таблица + фильтры (дата, статус, канал) + поиск по телефону |
| Карточка заказа | pages/order.py | Все поля, кнопки переходов, история, редактирование |
| Новый заказ | pages/new_order.py | Форма + поле «Разобрать с ИИ» |
| Сводка дня | pages/summary.py | 4 цифры: заказов, сумма, доставлено, отменено |

## 7. Модель данных (SQLite)

CREATE TABLE clients (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    phone_raw    TEXT,
    phone_norm   TEXT,
    comment      TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL REFERENCES clients(id),
    address         TEXT,
    items_text      TEXT,
    amount          REAL DEFAULT 0,
    prepayment      REAL DEFAULT 0,
    channel         TEXT,
    status          TEXT NOT NULL DEFAULT 'new',
    tracking_number TEXT,
    supplier        TEXT,
    comment         TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivered_at    TIMESTAMP,
    cancelled_at    TIMESTAMP,
    cancel_reason   TEXT
);

CREATE TABLE status_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL REFERENCES orders(id),
    from_status  TEXT,
    to_status    TEXT NOT NULL,
    comment      TEXT,
    changed_by   TEXT DEFAULT 'manager',
    changed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created ON orders(created_at);
CREATE INDEX idx_clients_phone ON clients(phone_norm);

### Нормализация телефона (обязательно)

import re

def norm_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    return digits[-10:] if len(digits) >= 10 else digits

## 8. Бизнес-правила

1. Телефон обязателен, нормализуется при сохранении.
2. 0 ≤ amount, 0 ≤ prepayment ≤ amount.
   Дефолт prepayment в форме = round(amount * 0.5, 2), поле редактируемое.
3. Смена статуса — только по ALLOWED_TRANSITIONS, иначе ValueError.
4. При переходе в delivered → delivered_at = now().
5. При переходе в cancelled → обязательна причина, cancelled_at = now().
6. Каждая смена статуса → запись в status_history.
7. Сводка дня не считает cancelled в сумму. Отменённые — отдельной цифрой.
8. Дата — по created_at (Europe/Moscow).

## 9. ИИ-функция (GigaChat)

Задача: менеджер вставляет текст → GigaChat возвращает JSON →
форма предзаполняется → менеджер правит → сохраняет.

System-промпт:

Ты — парсер заявок для службы доставки из Китая.
Из текста клиента извлеки JSON:
{"name": "...", "phone": "...", "address": "...", "items": "...", "amount": null, "channel": null}
Правила:
- phone — только цифры, 10 цифр без кода страны.
- address — как в тексте, не придумывай.
- items — список товаров через запятую.
- amount — число в рублях, если клиент назвал сумму. Иначе null.
- channel — avito|telegram|manual|null.
- Если поля нет в тексте — null. Только JSON, без пояснений.

Ошибки: таймаут/401/429 → st.error("GigaChat недоступен — заполните вручную"), форма остаётся доступной.
Невалидный JSON → пустая форма.

Безопасность: ключ только из .env как GIGACHAT_CREDENTIALS
(имя совпадает с документацией GigaChat и с прошлым проектом ChinaGoods).
.env в .gitignore, в репо — .env.example с плейсхолдером.

## 10. Критерии готовности (DoD)

- [ ] Заказ проходит все 4 статуса без ошибок.
- [ ] Попытка перескока/отката блокируется.
- [ ] Поиск находит заказ по телефону в любом формате (+7, 8, пробелы, скобки, дефисы).
- [ ] Фильтры «день + статус» работают вместе.
- [ ] Данные сохраняются после перезапуска Streamlit.
- [ ] Сумма дня = сумма заказов за день, без cancelled.
- [ ] Отменённые видны отдельной цифрой.
- [ ] Мобильная вёрстка не ломается на 390px.
- [ ] README с запуском и ограничениями.
- [ ] Скриншоты: список, карточка, сводка, мобильная версия.

## 11. Что НЕ входит в MVP

- Многопользовательский режим и роли.
- Курьер-режим.
- Интеграция с ботом ChinaGoods.
- Расчёт юань × курс + вес.
- Графики и аналитика за месяц.
- Уведомления клиенту.
- Дополнительные статусы (purchased, arrived_rf).
- Авторизация / логины.

## 12. Вторая версия

- Курьер-режим.
- Чтение заявок из бота ChinaGoods.
- Расчёт в юанях.
- Дашборд за 30 дней.
- Уведомления в Telegram.
- Дополнительные статусы.