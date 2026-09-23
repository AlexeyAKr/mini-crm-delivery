import pytest

from core.statuses import ALLOWED_TRANSITIONS, STATUS_LABELS, can_transition, validate_transition


@pytest.mark.parametrize("from_status,to_status", [
    ("new", "confirmed"),
    ("new", "cancelled"),
    ("confirmed", "in_transit"),
    ("confirmed", "cancelled"),
    ("in_transit", "delivered"),
    ("in_transit", "cancelled"),
])
def test_allowed_transitions(from_status, to_status):
    assert from_status in ALLOWED_TRANSITIONS
    assert can_transition(from_status, to_status) is True
    validate_transition(from_status, to_status)


@pytest.mark.parametrize("from_status,to_status", [
    ("new", "in_transit"),
    ("new", "delivered"),
    ("confirmed", "delivered"),
    ("confirmed", "new"),
    ("in_transit", "new"),
    ("in_transit", "confirmed"),
    ("delivered", "new"),
    ("delivered", "confirmed"),
    ("delivered", "in_transit"),
    ("delivered", "cancelled"),
    ("cancelled", "new"),
    ("cancelled", "confirmed"),
    ("cancelled", "in_transit"),
    ("cancelled", "delivered"),
])
def test_forbidden_transitions(from_status, to_status):
    assert can_transition(from_status, to_status) is False
    with pytest.raises(ValueError):
        validate_transition(from_status, to_status)


def test_unknown_status():
    assert can_transition("unknown", "new") is False
    with pytest.raises(ValueError):
        validate_transition("unknown", "new")


def test_status_labels_cover_all_statuses():
    assert set(STATUS_LABELS) == set(ALLOWED_TRANSITIONS)