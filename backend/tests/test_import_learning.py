"""Import feedback learning helpers."""
from services.import_learning import record_recipe_correction


def test_one_to_one_rename_only():
    out = record_recipe_correction(
        original_recipe={"ingredients": [{"name": "chinese fire"}]},
        corrected_recipe={"ingredients": [{"name": "Chinese five-spice"}]},
        import_id="imp_t1",
    )
    assert out["learned"] == 1
    assert out["pairs"][0]["good"].lower().startswith("chinese five")


def test_multi_add_does_not_pair_unrelated(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    out = record_recipe_correction(
        original_recipe={"ingredients": [{"name": "fish"}]},
        corrected_recipe={
            "ingredients": [
                {"name": "fish"},
                {"name": "kimchi"},
                {"name": "sriracha"},
            ]
        },
        import_id="imp_t2",
    )
    # fish still present — no rename pairs
    assert out["learned"] == 0
