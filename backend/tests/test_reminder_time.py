from utils.reminder_time import coerce_lead_minutes, lead_minutes_for_storage


def test_coerce_int_and_numeric_string():
    assert coerce_lead_minutes(30) == 30
    assert coerce_lead_minutes("60") == 60
    assert coerce_lead_minutes(15) == 15
    assert coerce_lead_minutes(120) == 120


def test_coerce_legacy_hhmm_to_minutes_before_18():
    assert coerce_lead_minutes("17:00") == 60
    assert coerce_lead_minutes("17:30") == 30
    assert coerce_lead_minutes("16:00") == 120


def test_coerce_defaults_and_out_of_range():
    assert coerce_lead_minutes(None) == 30
    assert coerce_lead_minutes("") == 30
    assert coerce_lead_minutes("nope") == 30
    assert coerce_lead_minutes(0) == 30
    assert coerce_lead_minutes(500) == 30
    assert coerce_lead_minutes(None, default=None) is None


def test_storage_is_minutes_string():
    assert lead_minutes_for_storage("17:00") == "60"
    assert lead_minutes_for_storage(30) == "30"
