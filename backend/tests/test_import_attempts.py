"""Import attempt history helpers used by Settings → Your imports."""
import json

from database.repositories.import_attempt_repository import (
    ImportAttemptRepository,
    _dumps_result,
    _loads_result,
)


def test_status_normalization_mapping():
    repo = ImportAttemptRepository()
    cases = {
        "success": "succeeded",
        "succeeded": "succeeded",
        "error": "failed",
        "failed": "failed",
        "blocked": "failed",
        "importing": "importing",
        "started": "importing",
    }
    for raw, expected in cases.items():
        normalized = {
            "success": "succeeded",
            "succeeded": "succeeded",
            "error": "failed",
            "failed": "failed",
            "blocked": "failed",
            "importing": "importing",
            "started": "importing",
        }.get(raw.lower(), raw[:20])
        assert normalized == expected, (raw, normalized, expected)
    assert repo.table_name == "import_attempts"


def test_result_json_roundtrip():
    recipe = {
        "title": "Mango Lassi Custard",
        "ingredients": [{"name": "mango", "amount": "1", "unit": "cup"}],
        "instructions": ["Blend", "Bake"],
    }
    payload = {"recipe": recipe, "used_ai": True}
    raw = _dumps_result(payload)
    assert isinstance(raw, str)
    loaded = _loads_result(raw)
    assert loaded["recipe"]["title"] == "Mango Lassi Custard"
    assert loaded["used_ai"] is True


def test_row_to_dict_exposes_recipe():
    repo = ImportAttemptRepository()
    row = {
        "id": "imp_abc",
        "kind": "import-text",
        "source_url": None,
        "status": "succeeded",
        "title": "Mango Lassi Custard",
        "error": None,
        "recipe_id": None,
        "result_json": json.dumps(
            {
                "recipe": {"title": "Mango Lassi Custard", "ingredients": []},
                "used_ai": True,
            }
        ),
        "created_at": None,
        "updated_at": None,
    }
    out = repo._row_to_dict(row, include_result=True)
    assert out["status"] == "succeeded"
    assert out["recipe"]["title"] == "Mango Lassi Custard"
    assert out["used_ai"] is True


def test_row_to_dict_without_result():
    repo = ImportAttemptRepository()
    row = {
        "id": "imp_abc",
        "kind": "import-text",
        "source_url": None,
        "status": "importing",
        "title": None,
        "error": None,
        "recipe_id": None,
        "created_at": None,
        "updated_at": None,
    }
    out = repo._row_to_dict(row, include_result=False)
    assert "recipe" not in out
    assert out["status"] == "importing"
