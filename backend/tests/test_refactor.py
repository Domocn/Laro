import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_imports():
    """Test that we can import the refactored modules"""
    try:
        from server import app
        from routers import auth, recipes
        from config import settings
        from models import UserCreate
    except ImportError as e:
        pytest.fail(f"Import failed: {e}")


def test_config_defaults():
    from config import settings
    assert settings.database_url is not None  # PostgreSQL connection URL
    assert settings.jwt_algorithm == "HS256"


def test_router_prefixes():
    from routers import auth, recipes, ai
    assert auth.router.prefix == "/auth"
    assert recipes.router.prefix == "/recipes"
    assert ai.router.prefix == "/ai"
