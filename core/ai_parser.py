import json
import logging
import re

from gigachat import GigaChat
from gigachat.models import ChatCompletionRequest, ChatMessage

from core.config import GIGACHAT_CREDENTIALS, GIGACHAT_SCOPE

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """РўС‹ вЂ” РїР°СЂСЃРµСЂ Р·Р°СЏРІРѕРє РґР»СЏ СЃР»СѓР¶Р±С‹ РґРѕСЃС‚Р°РІРєРё РёР· РљРёС‚Р°СЏ.
РР· С‚РµРєСЃС‚Р° РєР»РёРµРЅС‚Р° РёР·РІР»РµРєРё JSON:
{"name": "...", "phone": "...", "address": "...", "items": "...", "amount": null, "channel": null}
РџСЂР°РІРёР»Р°:
- phone вЂ” С‚РѕР»СЊРєРѕ С†РёС„СЂС‹, 10 С†РёС„СЂ Р±РµР· РєРѕРґР° СЃС‚СЂР°РЅС‹.
- address вЂ” РєР°Рє РІ С‚РµРєСЃС‚Рµ, РЅРµ РїСЂРёРґСѓРјС‹РІР°Р№.
- items вЂ” СЃРїРёСЃРѕРє С‚РѕРІР°СЂРѕРІ С‡РµСЂРµР· Р·Р°РїСЏС‚СѓСЋ.
- amount вЂ” С‡РёСЃР»Рѕ РІ СЂСѓР±Р»СЏС…, РµСЃР»Рё РєР»РёРµРЅС‚ РЅР°Р·РІР°Р» СЃСѓРјРјСѓ. РРЅР°С‡Рµ null.
- channel вЂ” avito|telegram|manual|null.
- Р•СЃР»Рё РїРѕР»СЏ РЅРµС‚ РІ С‚РµРєСЃС‚Рµ вЂ” null. РўРѕР»СЊРєРѕ JSON, Р±РµР· РїРѕСЏСЃРЅРµРЅРёР№."""

_EXPECTED_KEYS = ("name", "phone", "address", "items", "amount", "channel")


class GigaChatUnavailableError(Exception):
    """GigaChat РЅРµРґРѕСЃС‚СѓРїРµРЅ (С‚Р°Р№РјР°СѓС‚, 401, 429 Рё С‚.Рї.)."""


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

    request = ChatCompletionRequest(
        model="GigaChat-2",
        messages=[
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=text),
        ],
    )

    try:
        with GigaChat(
            credentials=GIGACHAT_CREDENTIALS,
            scope=GIGACHAT_SCOPE,
            verify_ssl_certs=False,
            timeout=30,
        ) as giga:
            response = giga.chat.create(request)
    except Exception as exc:
        logger.warning("GigaChat request failed: %s", exc)
        raise GigaChatUnavailableError from exc

    return _extract_json(response.messages[0].content[0].text)
