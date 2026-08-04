import pytest
from pathlib import Path
from fastapi import HTTPException
from unittest.mock import MagicMock
import sys
import os

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_path_traversal_logic():
    # Simulate UPLOAD_DIR
    UPLOAD_DIR = Path("/app/uploads").resolve()

    def get_upload_logic(filename):
        try:
            file_path = (UPLOAD_DIR / filename).resolve()
            if not file_path.is_relative_to(UPLOAD_DIR):
                raise ValueError("Path traversal detected")
            return file_path
        except ValueError:
            raise HTTPException(status_code=404, detail="File not found")

    # Safe path
    assert get_upload_logic("test.jpg") == UPLOAD_DIR / "test.jpg"

    # Unsafe path
    try:
        get_upload_logic("../../etc/passwd")
        assert False, "Should have raised HTTPException"
    except HTTPException as e:
        assert e.status_code == 404

def test_extension_whitelist_logic():
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}

    def validate_extension(filename):
        ext = filename.split(".")[-1].lower() if filename else "jpg"
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError("Invalid file type")
        return ext

    assert validate_extension("test.jpg") == "jpg"
    assert validate_extension("test.PNG") == "png"

    try:
        validate_extension("test.php")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    try:
        validate_extension("test.exe")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
