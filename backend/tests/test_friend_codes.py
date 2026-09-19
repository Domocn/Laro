from utils.friend_codes import (
    FOOD_WORDS,
    generate_friend_code,
    normalize_friend_code,
    friend_code_lookup_variants,
)


def test_generate_friend_code_format():
    for _ in range(30):
        code = generate_friend_code()
        assert " " in code
        word, num = code.split(" ", 1)
        assert word in FOOD_WORDS
        assert num.isdigit() and 10 <= int(num) <= 99


def test_normalize_friend_code_variants():
    assert normalize_friend_code("tomato 44") == "TOMATO 44"
    assert normalize_friend_code("TOMATO44") == "TOMATO 44"
    assert normalize_friend_code("tomato#44") == "TOMATO 44"
    assert normalize_friend_code("  basil  7 ") == "BASIL 7"


def test_lookup_variants_include_legacy():
    variants = friend_code_lookup_variants("chef#1234")
    assert "CHEF#1234" in variants
    assert "CHEF 1234" in variants
