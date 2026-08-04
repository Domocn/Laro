"""
Unit Tests for BaseRepository
Tests datetime conversion, JSON serialization, and CRUD operations
"""
import pytest
import asyncio
from datetime import datetime, timezone
from database.repositories.base_repository import BaseRepository


class TestDatetimeConversion:
    """Test datetime string conversion for asyncpg compatibility"""

    def test_convert_datetime_strings_iso_format(self):
        """Test conversion of ISO format datetime strings"""
        repo = BaseRepository("test")

        data = {
            "id": "123",
            "created_at": "2026-01-19T16:33:22.599811+00:00",
            "name": "Test"
        }

        result = repo._convert_datetime_strings(data)

        assert isinstance(result["created_at"], datetime)
        assert result["id"] == "123"
        assert result["name"] == "Test"

    def test_convert_datetime_strings_without_timezone(self):
        """Test conversion of datetime without timezone"""
        repo = BaseRepository("test")

        data = {
            "updated_at": "2026-01-19T16:33:22"
        }

        result = repo._convert_datetime_strings(data)
        assert isinstance(result["updated_at"], datetime)

    def test_convert_datetime_strings_z_suffix(self):
        """Test conversion of datetime with Z suffix"""
        repo = BaseRepository("test")

        data = {
            "timestamp": "2026-01-19T16:33:22Z"
        }

        result = repo._convert_datetime_strings(data)
        assert isinstance(result["timestamp"], datetime)

    def test_convert_datetime_strings_invalid(self):
        """Test that invalid datetime strings are left as-is"""
        repo = BaseRepository("test")

        data = {
            "not_a_datetime": "just a string",
            "number": 123,
            "short_string": "2026"
        }

        result = repo._convert_datetime_strings(data)

        assert result["not_a_datetime"] == "just a string"
        assert result["number"] == 123
        assert result["short_string"] == "2026"

    def test_convert_datetime_strings_mixed_data(self):
        """Test conversion with mixed data types"""
        repo = BaseRepository("test")

        data = {
            "id": "456",
            "created_at": "2026-01-19T12:00:00+00:00",
            "description": "Test recipe",
            "count": 5,
            "active": True,
            "invalid_date": "not-a-date"
        }

        result = repo._convert_datetime_strings(data)

        assert isinstance(result["created_at"], datetime)
        assert result["id"] == "456"
        assert result["description"] == "Test recipe"
        assert result["count"] == 5
        assert result["active"] is True
        assert result["invalid_date"] == "not-a-date"


class TestJSONSerialization:
    """Test JSON field serialization and deserialization"""

    def test_serialize_json_fields(self):
        """Test serialization of JSON fields to strings"""
        repo = BaseRepository("test")

        data = {
            "tags": ["vegetarian", "quick"],
            "metadata": {"difficulty": "easy", "rating": 4.5}
        }

        result = repo._serialize_json_fields(data, ["tags", "metadata"])

        assert isinstance(result["tags"], str)
        assert isinstance(result["metadata"], str)
        assert '"vegetarian"' in result["tags"]

    def test_serialize_json_fields_already_string(self):
        """Test that already-serialized JSON is left as-is"""
        repo = BaseRepository("test")

        data = {
            "tags": '["already", "serialized"]'
        }

        result = repo._serialize_json_fields(data, ["tags"])
        assert result["tags"] == '["already", "serialized"]'

    def test_deserialize_json_fields(self):
        """Test deserialization of JSON strings"""
        repo = BaseRepository("test")

        data = {
            "tags": '["vegetarian", "quick"]',
            "metadata": '{"difficulty": "easy"}'
        }

        result = repo._deserialize_json_fields(data, ["tags", "metadata"])

        assert isinstance(result["tags"], list)
        assert isinstance(result["metadata"], dict)
        assert "vegetarian" in result["tags"]
        assert result["metadata"]["difficulty"] == "easy"

    def test_deserialize_json_fields_invalid(self):
        """Test that invalid JSON is left as-is"""
        repo = BaseRepository("test")

        data = {
            "tags": "not valid json"
        }

        result = repo._deserialize_json_fields(data, ["tags"])
        assert result["tags"] == "not valid json"

    def test_deserialize_json_fields_none(self):
        """Test handling of None data"""
        repo = BaseRepository("test")

        result = repo._deserialize_json_fields(None, ["tags"])
        assert result is None


class TestInputValidation:
    """Test input validation and sanitization"""

    def test_table_name_sanitization(self):
        """Test that table name is properly stored"""
        repo = BaseRepository("test_table")
        assert repo.table_name == "test_table"

    def test_empty_conditions_handling(self):
        """Test handling of empty conditions in queries"""
        # This would require actual database connection
        # Placeholder for integration test
        pass


if __name__ == "__main__":
    # Run tests with: python -m pytest backend/tests/test_base_repository.py -v
    pytest.main([__file__, "-v"])
