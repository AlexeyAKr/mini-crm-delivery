ALLOWED_TRANSITIONS = {
    "new": ["confirmed", "cancelled"],
    "confirmed": ["in_transit", "cancelled"],
    "in_transit": ["delivered", "cancelled"],
    "delivered": [],
    "cancelled": [],
}

STATUS_LABELS = {
    "new": "Новый",
    "confirmed": "Подтверждён",
    "in_transit": "В пути",
    "delivered": "Доставлен",
    "cancelled": "Отменён",
}


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, [])


def validate_transition(from_status: str, to_status: str) -> None:
    if not can_transition(from_status, to_status):
        raise ValueError(
            f"Переход {from_status} -> {to_status} запрещён"
        )