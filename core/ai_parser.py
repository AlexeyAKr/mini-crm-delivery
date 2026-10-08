import json
import logging
import re
import uuid

import requests
import urllib3

from core.config import GIGACHAT_CREDENTIALS, GIGACHAT_SCOPE

urllib3.disable_warnings()

logger = logging.getLogger(__name__)

_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
_CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
_MODEL = "GigaChat"
_FALLBACK_MODEL = "GigaChat-Pro"
_REQUEST_TIMEOUT = 30

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


def _raise_unavailable(exc: Exception, response: requests.Response | None = None) -> None:
    logger.warning("GigaChat request failed: %s", exc)
    error_response = getattr(exc, "response", None)
    if error_response is None:
        error_response = response
    request_id = (
        error_response.headers.get("x-request-id")
        if error_response is not None
        else None
    )
    if request_id:
        logger.warning("GigaChat request_id: %s", request_id)
    raise GigaChatUnavailableError from exc


def _get_access_token() -> str:
    response = None
    try:
        response = requests.post(
            _OAUTH_URL,
            headers={
                "Authorization": f"Basic {GIGACHAT_CREDENTIALS}",
                "RqUID": str(uuid.uuid4()),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={"scope": GIGACHAT_SCOPE},
            verify=False,
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        access_token = response.json()["access_token"]
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("GigaChat OAuth response has no access token")
        return access_token
    except Exception as exc:
        _raise_unavailable(exc, response)


def _request_chat_completion(access_token: str, text: str) -> str:
    response = None
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": _MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        }
        response = requests.post(
            _CHAT_URL, headers=headers, json=payload,
            verify=False, timeout=_REQUEST_TIMEOUT,
        )
        if response.status_code == 404:
            payload["model"] = _FALLBACK_MODEL
            response = None
            response = requests.post(
                _CHAT_URL, headers=headers, json=payload,
                verify=False, timeout=_REQUEST_TIMEOUT,
            )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ValueError("GigaChat response content is not a string")
        return content
    except Exception as exc:
        _raise_unavailable(exc, response)


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
    access_token = _get_access_token()
    content = _request_chat_completion(access_token, text)
    return _extract_json(content)
