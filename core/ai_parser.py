import json
import logging
import re

from gigachat import GigaChat
from gigachat.models import Messages, MessagesRole

from core.config import GIGACHAT_CREDENTIALS, GIGACHAT_SCOPE

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Ты — парсер заявок для службы доставки из Китая.
Из текста клиента извлеки JSON:
{"name": "...", "phone": "...", "address": "...", "items": "...", "amount": null, "channel": null}
Правила:
- phone — только цифры, 10 цифр без кода страны.
- address — как в тексте, не придумывай.
- items — список товаров через запятую.
- amount — число в рублях, если клиент назвал сумму. Иначе null.
- channel — avito|telegram|manual|null.
- Если поля нет в тексте — null. Только JSON, без пояснений."""

_EXPECTED_KEYS = ("name", "phone", "address", "items", "amount", "channel")


class GigaChatUnavailableError(Exception):
    """GigaChat недоступен (таймаут, 401, 429 и т.п.)."""


def _extract_json(content: str) -> dict | None:
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return {key: data.get(key) for key in _EXPECTED_KEYS}


def parse_request(text: str) -> dict | None:
    if not text or not text.strip():
        return None
    messages = [
        Messages(role=MessagesRole.SYSTEM, content=_SYSTEM_PROMPT),
        Messages(role=MessagesRole.USER, content=text),
    ]
    try:
        with GigaChat(
            credentials=GIGACHAT_CREDENTIALS,
            scope=GIGACHAT_SCOPE,
            model="GigaChat-2",
            verify_ssl_certs=False,
            timeout=30,
        ) as giga:
            response = giga.chat.create(messages=messages)
    except Exception as exc:
        logger.warning("GigaChat request failed: %s", exc)
        raise GigaChatUnavailableError from exc
    return _extract_json(response.messages[0].content[0].text)