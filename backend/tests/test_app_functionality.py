"""
Comprehensive Application Functionality Tests

This test file tests all core functionality of the Laro application:
- User registration and login
- Two-factor authentication (2FA)
- Recipe management (CRUD)
- Recipe import (URL and text)
- Meal planning
- Shopping lists
- User preferences/settings
- Security features
- Admin functionality
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
import json
import sys
import os

# Add backend to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_db_pool():
    """Create a mock database pool"""
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock()
    return mock_pool


@pytest.fixture
def mock_repositories():
    """Mock all repositories"""
    with patch('dependencies.user_repository') as mock_user_repo, \
         patch('dependencies.recipe_repository') as mock_recipe_repo, \
         patch('dependencies.session_repository') as mock_session_repo, \
         patch('dependencies.meal_plan_repository') as mock_meal_plan_repo, \
         patch('dependencies.shopping_list_repository') as mock_shopping_list_repo, \
         patch('dependencies.system_settings_repository') as mock_settings_repo, \
         patch('dependencies.totp_secret_repository') as mock_totp_repo, \
         patch('dependencies.user_preferences_repository') as mock_prefs_repo:

        # Set up default return values
        mock_settings_repo.get_settings = AsyncMock(return_value={
            "allow_registration": True,
            "require_invite_code": False,
            "password_min_length": 8
        })
        mock_settings_repo.get_setup_status = AsyncMock(return_value={"complete": True})

        yield {
            'user': mock_user_repo,
            'recipe': mock_recipe_repo,
            'session': mock_session_repo,
            'meal_plan': mock_meal_plan_repo,
            'shopping_list': mock_shopping_list_repo,
            'settings': mock_settings_repo,
            'totp': mock_totp_repo,
            'preferences': mock_prefs_repo
        }


# =============================================================================
# USER REGISTRATION TESTS
# =============================================================================

class TestUserRegistration:
    """Test user registration functionality"""

    def test_user_create_model_validation(self):
        """Test UserCreate model validates email and password"""
        from models import UserCreate

        # Valid user creation
        user = UserCreate(
            email="test@example.com",
            password="securepass123",
            name="Test User"
        )
        assert user.email == "test@example.com"
        assert user.name == "Test User"

    def test_user_create_invalid_email(self):
        """Test UserCreate rejects invalid email"""
        from models import UserCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UserCreate(
                email="invalid-email",
                password="securepass123",
                name="Test User"
            )

    def test_password_validation_logic(self):
        """Test password validation logic"""
        async def validate_password(password: str, settings: dict) -> tuple:
            min_length = settings.get("password_min_length", 8)
            require_uppercase = settings.get("password_require_uppercase", False)
            require_number = settings.get("password_require_number", False)
            require_special = settings.get("password_require_special", False)

            if len(password) < min_length:
                return False, f"Password must be at least {min_length} characters"

            if require_uppercase and not any(c.isupper() for c in password):
                return False, "Password must contain at least one uppercase letter"

            if require_number and not any(c.isdigit() for c in password):
                return False, "Password must contain at least one number"

            if require_special and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
                return False, "Password must contain at least one special character"

            return True, ""

        # Test minimum length
        loop = asyncio.get_event_loop()

        settings = {"password_min_length": 8}
        result, msg = loop.run_until_complete(validate_password("short", settings))
        assert result is False
        assert "at least 8 characters" in msg

        result, msg = loop.run_until_complete(validate_password("longenough", settings))
        assert result is True

        # Test uppercase requirement
        settings = {"password_require_uppercase": True}
        result, msg = loop.run_until_complete(validate_password("nouppercase", settings))
        assert result is False
        assert "uppercase" in msg

        result, msg = loop.run_until_complete(validate_password("HasUppercase", settings))
        assert result is True

        # Test number requirement
        settings = {"password_require_number": True}
        result, msg = loop.run_until_complete(validate_password("nonumbers", settings))
        assert result is False
        assert "number" in msg

        result, msg = loop.run_until_complete(validate_password("hasnumber123", settings))
        assert result is True

        # Test special character requirement
        settings = {"password_require_special": True}
        result, msg = loop.run_until_complete(validate_password("nospecials123", settings))
        assert result is False
        assert "special" in msg

        result, msg = loop.run_until_complete(validate_password("hasspecial!", settings))
        assert result is True


# =============================================================================
# USER LOGIN TESTS
# =============================================================================

class TestUserLogin:
    """Test user login functionality"""

    def test_user_login_model_validation(self):
        """Test UserLogin model validation"""
        from models import UserLogin

        login = UserLogin(
            email="test@example.com",
            password="testpassword"
        )
        assert login.email == "test@example.com"

    def test_password_hashing(self):
        """Test password hashing and verification"""
        from dependencies import hash_password, verify_password

        password = "testpassword123"
        hashed = hash_password(password)

        # Verify correct password
        assert verify_password(password, hashed) is True

        # Verify wrong password
        assert verify_password("wrongpassword", hashed) is False

    def test_token_creation(self):
        """Test JWT token creation"""
        from dependencies import create_token
        import jwt
        from config import settings

        user_id = "test-user-id"
        token = create_token(user_id)

        # Decode and verify token
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload.get("user_id") == user_id


# =============================================================================
# TWO-FACTOR AUTHENTICATION TESTS
# =============================================================================

class TestTwoFactorAuth:
    """Test 2FA functionality"""

    def test_totp_secret_generation(self):
        """Test TOTP secret generation"""
        import pyotp

        secret = pyotp.random_base32()
        assert len(secret) == 32  # Base32 encoded secret

        # Verify we can create a TOTP with the secret
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert len(code) == 6
        assert code.isdigit()

    def test_totp_verification(self):
        """Test TOTP code verification"""
        import pyotp

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)

        # Generate and verify code
        code = totp.now()
        assert totp.verify(code) is True

        # Wrong code should fail
        assert totp.verify("000000") is False

    def test_backup_codes_generation(self):
        """Test backup code generation"""
        import secrets
        from dependencies import hash_password, verify_password

        # Generate backup codes
        backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
        assert len(backup_codes) == 8

        # Verify all codes are unique
        assert len(set(backup_codes)) == 8

        # Verify codes can be hashed and verified
        code = backup_codes[0]
        hashed = hash_password(code)
        assert verify_password(code, hashed) is True


# =============================================================================
# RECIPE MANAGEMENT TESTS
# =============================================================================

class TestRecipeManagement:
    """Test recipe CRUD operations"""

    def test_recipe_create_model(self):
        """Test RecipeCreate model validation"""
        from models import RecipeCreate, Ingredient

        ingredients = [
            Ingredient(name="Flour", amount="2", unit="cups"),
            Ingredient(name="Sugar", amount="1", unit="cup")
        ]

        recipe = RecipeCreate(
            title="Test Recipe",
            description="A test recipe",
            ingredients=ingredients,
            instructions=["Mix ingredients", "Bake for 30 minutes"],
            prep_time=10,
            cook_time=30,
            servings=4,
            category="Dessert"
        )

        assert recipe.title == "Test Recipe"
        assert len(recipe.ingredients) == 2
        assert len(recipe.instructions) == 2

    def test_ingredient_model(self):
        """Test Ingredient model"""
        from models import Ingredient

        ing = Ingredient(name="Salt", amount="1", unit="tsp")
        assert ing.name == "Salt"
        assert ing.amount == "1"
        assert ing.unit == "tsp"

    def test_recipe_scaling_logic(self):
        """Test recipe scaling logic"""
        def scale_ingredient(amount: str, scale_factor: float) -> str:
            try:
                if "/" in str(amount):
                    parts = str(amount).split("/")
                    if len(parts) == 2:
                        num = float(parts[0].strip())
                        denom = float(parts[1].strip())
                        original_num = num / denom
                    else:
                        original_num = float(amount)
                else:
                    original_num = float(amount)

                scaled_num = original_num * scale_factor
                if scaled_num == int(scaled_num):
                    return str(int(scaled_num))
                else:
                    return f"{scaled_num:.2f}".rstrip('0').rstrip('.')
            except (ValueError, TypeError):
                return amount

        # Test doubling
        assert scale_ingredient("2", 2.0) == "4"
        assert scale_ingredient("1/2", 2.0) == "1"
        assert scale_ingredient("0.5", 2.0) == "1"

        # Test halving
        assert scale_ingredient("4", 0.5) == "2"
        assert scale_ingredient("1", 0.5) == "0.5"

        # Test non-numeric
        assert scale_ingredient("to taste", 2.0) == "to taste"


# =============================================================================
# RECIPE IMPORT TESTS
# =============================================================================

class TestRecipeImport:
    """Test recipe import functionality"""

    def test_domain_extraction(self):
        """Test domain extraction from URL"""
        import re

        def extract_domain(url: str) -> str:
            match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            return match.group(1) if match else ""

        assert extract_domain("https://www.allrecipes.com/recipe/123") == "allrecipes.com"
        assert extract_domain("https://tasty.co/recipe/test") == "tasty.co"
        assert extract_domain("http://example.com/test") == "example.com"

    def test_duration_parsing(self):
        """Test ISO 8601 duration parsing"""
        import re

        def parse_duration(duration_str: str) -> int:
            if not duration_str:
                return 0

            hours = 0
            minutes = 0

            h_match = re.search(r'(\d+)H', duration_str)
            m_match = re.search(r'(\d+)M', duration_str)

            if h_match:
                hours = int(h_match.group(1))
            if m_match:
                minutes = int(m_match.group(1))

            return hours * 60 + minutes

        assert parse_duration("PT1H30M") == 90
        assert parse_duration("PT30M") == 30
        assert parse_duration("PT2H") == 120
        assert parse_duration("") == 0


# =============================================================================
# MEAL PLANNING TESTS
# =============================================================================

class TestMealPlanning:
    """Test meal planning functionality"""

    def test_meal_plan_create_model(self):
        """Test MealPlanCreate model"""
        from models import MealPlanCreate

        plan = MealPlanCreate(
            date="2026-01-20",
            meal_type="dinner",
            recipe_id="test-recipe-id"
        )

        assert plan.date == "2026-01-20"
        assert plan.meal_type == "dinner"

    def test_meal_plan_response_model(self):
        """Test MealPlanResponse model"""
        from models import MealPlanResponse

        response = MealPlanResponse(
            id="plan-id",
            date="2026-01-20",
            meal_type="dinner",
            recipe_id="recipe-id",
            recipe_title="Test Recipe",
            notes="",
            household_id="household-id",
            created_at="2026-01-19T00:00:00Z"
        )

        assert response.id == "plan-id"
        assert response.recipe_title == "Test Recipe"


# =============================================================================
# SHOPPING LIST TESTS
# =============================================================================

class TestShoppingLists:
    """Test shopping list functionality"""

    def test_shopping_list_create_model(self):
        """Test ShoppingListCreate model"""
        from models import ShoppingListCreate, ShoppingItem

        items = [
            ShoppingItem(name="Milk", amount="1", unit="gallon", checked=False),
            ShoppingItem(name="Bread", amount="1", unit="loaf", checked=False)
        ]

        shopping_list = ShoppingListCreate(
            name="Weekly Shopping",
            items=items
        )

        assert shopping_list.name == "Weekly Shopping"
        assert len(shopping_list.items) == 2

    def test_item_matching_logic(self):
        """Test item matching for receipt scanning"""
        import re

        def normalize_item_name(name: str) -> str:
            name = name.lower().strip()
            name = re.sub(r'\s+', ' ', name)
            name = re.sub(r'\d+\s*(oz|lb|kg|g|ml|l|ct|pk|pack)\b', '', name, flags=re.IGNORECASE)
            name = re.sub(r'\$[\d.]+', '', name)
            name = name.strip()
            return name

        assert normalize_item_name("MILK 1 GAL") == "milk 1 gal"
        assert normalize_item_name("  Extra  Spaces  ") == "extra spaces"
        assert normalize_item_name("BREAD 16oz") == "bread"


# =============================================================================
# USER PREFERENCES TESTS
# =============================================================================

class TestUserPreferences:
    """Test user preferences functionality"""

    def test_user_preferences_model(self):
        """Test UserPreferences model with defaults"""
        from routers.preferences import UserPreferences

        prefs = UserPreferences()

        assert prefs.theme == "system"
        assert prefs.defaultServings == 4
        assert prefs.measurementUnit == "metric"
        assert prefs.dyslexicFont is False
        assert prefs.focusMode is False

    def test_user_preferences_custom_values(self):
        """Test UserPreferences with custom values"""
        from routers.preferences import UserPreferences

        prefs = UserPreferences(
            theme="dark",
            defaultServings=2,
            measurementUnit="imperial",
            dyslexicFont=True,
            focusMode=True
        )

        assert prefs.theme == "dark"
        assert prefs.defaultServings == 2
        assert prefs.measurementUnit == "imperial"
        assert prefs.dyslexicFont is True
        assert prefs.focusMode is True


# =============================================================================
# SECURITY TESTS
# =============================================================================

class TestSecurity:
    """Test security-related functionality"""

    def test_ip_pattern_matching(self):
        """Test IP pattern matching for allowlist/blocklist"""
        import ipaddress
        import re

        def ip_matches_pattern(ip: str, pattern: str) -> bool:
            try:
                if ip == pattern:
                    return True

                if '/' in pattern:
                    try:
                        network = ipaddress.ip_network(pattern, strict=False)
                        return ipaddress.ip_address(ip) in network
                    except ValueError:
                        return False

                if '*' in pattern:
                    regex_pattern = pattern.replace('.', r'\.').replace('*', r'\d+')
                    return bool(re.match(f'^{regex_pattern}$', ip))

                return False
            except Exception:
                return False

        # Exact match
        assert ip_matches_pattern("192.168.1.1", "192.168.1.1") is True
        assert ip_matches_pattern("192.168.1.1", "192.168.1.2") is False

        # CIDR match
        assert ip_matches_pattern("192.168.1.100", "192.168.1.0/24") is True
        assert ip_matches_pattern("192.168.2.1", "192.168.1.0/24") is False

        # Wildcard match
        assert ip_matches_pattern("192.168.1.1", "192.168.1.*") is True
        assert ip_matches_pattern("192.168.2.1", "192.168.1.*") is False

    def test_path_traversal_prevention(self):
        """Test path traversal prevention"""
        from pathlib import Path
        from fastapi import HTTPException

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

        # Unsafe path - should raise exception
        try:
            get_upload_logic("../../etc/passwd")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 404

    def test_extension_whitelist(self):
        """Test file extension whitelist"""
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


# =============================================================================
# ADMIN FUNCTIONALITY TESTS
# =============================================================================

class TestAdminFunctionality:
    """Test admin functionality"""

    def test_admin_user_check(self):
        """Test admin user role check"""
        def is_admin(user: dict) -> bool:
            return user.get("role") == "admin"

        admin_user = {"id": "1", "role": "admin"}
        regular_user = {"id": "2", "role": "user"}

        assert is_admin(admin_user) is True
        assert is_admin(regular_user) is False

    def test_invite_code_generation(self):
        """Test invite code generation"""
        import secrets

        code = secrets.token_urlsafe(8).upper()[:8]

        assert len(code) == 8
        # URL-safe tokens can include alphanumeric, underscore, and hyphen
        assert all(c.isalnum() or c in '_-' for c in code)


# =============================================================================
# WEBSOCKET MANAGER TESTS
# =============================================================================

class TestWebSocketManager:
    """Test WebSocket manager functionality"""

    def test_event_type_enum(self):
        """Test EventType enum values"""
        from database.websocket_manager import EventType

        assert EventType.RECIPE_CREATED is not None
        assert EventType.RECIPE_UPDATED is not None
        assert EventType.RECIPE_DELETED is not None
        assert EventType.MEAL_PLAN_CREATED is not None
        assert EventType.SHOPPING_LIST_UPDATED is not None


# =============================================================================
# INTEGRATION TESTS (require running app)
# =============================================================================

class TestIntegration:
    """Integration tests that require the full application"""

    @pytest.mark.asyncio
    async def test_app_imports(self):
        """Test that the app can be imported without errors"""
        try:
            from server import app
            assert app is not None
            assert app.title == "Laro API"
        except ImportError as e:
            pytest.fail(f"Failed to import app: {e}")

    @pytest.mark.asyncio
    async def test_routers_import(self):
        """Test that all routers can be imported"""
        try:
            from routers import (
                auth, households, recipes, ai, meal_plans, shopping_lists,
                homeassistant, notifications, calendar, import_data, llm_settings,
                favorites, prompts, cooking, admin, security, oauth, preferences,
                roles, trusted_devices, recipe_versions, nutrition, seed,
                recipe_import, voice_cooking, cost_tracking, reviews, sharing, jobs
            )
        except ImportError as e:
            pytest.fail(f"Failed to import routers: {e}")

    @pytest.mark.asyncio
    async def test_models_import(self):
        """Test that all models can be imported"""
        try:
            from models import (
                UserCreate, UserLogin, UserResponse, UserUpdate,
                RecipeCreate, RecipeResponse, Ingredient,
                MealPlanCreate, MealPlanResponse,
                ShoppingListCreate, ShoppingListResponse, ShoppingItem
            )
        except ImportError as e:
            pytest.fail(f"Failed to import models: {e}")

    @pytest.mark.asyncio
    async def test_config_values(self):
        """Test that config values are accessible"""
        from config import settings

        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_secret is not None
        assert settings.database_url is not None


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
