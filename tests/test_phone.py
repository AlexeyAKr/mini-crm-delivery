import pytest

from core.phone import format_phone, norm_phone


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("+7 912 345 67 89", "9123456789"),
        ("8 912 345 67 89", "9123456789"),
        ("+7 (912) 345-67-89", "9123456789"),
        ("8(912)345-67-89", "9123456789"),
        ("  8  912  345  67  89  ", "9123456789"),
        ("79123456789", "9123456789"),
        ("9123456789", "9123456789"),
        ("123456789", "123456789"),
        ("", ""),
        (None, ""),
    ],
)
def test_norm_phone(raw, expected):
    assert norm_phone(raw) == expected


def test_format_phone_roundtrip():
    assert format_phone("+7 (912) 345-67-89") == "+7 (912) 345-67-89"


def test_format_phone_short():
    assert format_phone("12345") == "12345"