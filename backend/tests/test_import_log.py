"""Unit tests for structured import tracing."""
import json
from pathlib import Path

from services.import_log import ImportTrace, recipe_summary


def test_import_trace_writes_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORT_LOG_DIR", str(tmp_path))

    trace = ImportTrace(
        "import-url",
        user_id="user-1",
        url="https://www.instagram.com/reel/abc/",
        extra={"client": "test"},
    )
    import_id = trace.import_id
    assert import_id.startswith("imp_")

    trace.step("ig_resolve_done", source="socialfetch", has_video=True)
    summary = trace.finish("success", mode="reel", title="Test Oats")

    assert summary["import_id"] == import_id
    assert summary["status"] == "success"
    assert summary["elapsed_ms"] >= 0

    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 3  # start + step + finish

    records = [json.loads(line) for line in lines]
    assert all(r["import_id"] == import_id for r in records)
    steps = [r["step"] for r in records]
    assert steps[0] == "start"
    assert "ig_resolve_done" in steps
    assert steps[-1] == "finish"
    assert records[-1]["data"]["status"] == "success"
    assert records[-1]["data"]["mode"] == "reel"


def test_recipe_summary():
    assert recipe_summary(None) == {"empty": True}
    assert recipe_summary(
        {
            "title": "Snickers Baked Oats",
            "ingredients": [{"name": "oats"}, {"name": "milk"}],
            "instructions": ["mix", "bake"],
            "nutrition": {"calories": 400},
        }
    ) == {
        "title": "Snickers Baked Oats",
        "ingredients": 2,
        "instructions": 2,
        "has_nutrition": True,
    }
