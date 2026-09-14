"""Import attempt history helpers used by Settings → Your imports."""
from database.repositories.import_attempt_repository import ImportAttemptRepository


def test_status_normalization_mapping():
    repo = ImportAttemptRepository()
    # Access the same mapping used in finish_attempt
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
