import re

_DIGITS_ONLY = re.compile(r"\D")


def norm_phone(raw: str) -> str:
    digits = _DIGITS_ONLY.sub("", raw or "")
    return digits[-10:] if len(digits) >= 10 else digits


def format_phone(raw: str) -> str:
    norm = norm_phone(raw)
    if len(norm) != 10:
        return norm
    return f"+7 ({norm[:3]}) {norm[3:6]}-{norm[6:8]}-{norm[8:]}"