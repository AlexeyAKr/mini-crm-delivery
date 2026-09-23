from core.ai_parser import _extract_json, parse_request


def test_extract_json_plain():
    result = _extract_json('{"name": "Иван", "phone": "9123456789", "amount": 100}')
    assert result == {
        "name": "Иван",
        "phone": "9123456789",
        "address": None,
        "items": None,
        "amount": 100,
        "channel": None,
    }


def test_extract_json_code_fence():
    content = 'Ответ:\n```json\n{"name": "Иван", "items": "Кружка, бутылка"}\n```'
    result = _extract_json(content)
    assert result["name"] == "Иван"
    assert result["items"] == "Кружка, бутылка"


def test_extract_json_invalid():
    assert _extract_json("no json here") is None
    assert _extract_json("{broken") is None
    assert _extract_json("{broken}") is None
    assert _extract_json("[1, 2, 3]") is None


def test_parse_request_empty_text():
    assert parse_request("") is None
    assert parse_request("   ") is None
    assert parse_request(None) is None