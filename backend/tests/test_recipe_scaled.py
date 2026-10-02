import pytest

from utils.ingredient_parse import format_scaled_amount, parse_amount_to_float


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2", 2.0),
        ("1.5", 1.5),
        ("1/2", 0.5),
        ("1 1/2", 1.5),
        ("½", 0.5),
        ("", None),
        ("to taste", None),
    ],
)
def test_parse_amount_to_float(raw, expected):
    assert parse_amount_to_float(raw) == expected


def test_format_scaled_amount():
    assert format_scaled_amount(2.0) == "2"
    assert format_scaled_amount(1.5) == "1.5"
