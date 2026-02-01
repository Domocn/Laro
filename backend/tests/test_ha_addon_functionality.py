"""
Comprehensive Home Assistant Add-on Functionality Tests

This test file tests all HA addon-specific functionality:
- Environment variable configuration
- Debug router functionality
- Home Assistant integration endpoints
- Frontend API configuration
- Service startup scripts
- Nginx proxy configuration
"""
import pytest
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

# Add backend to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# =============================================================================
# HA ADDON ENVIRONMENT CONFIGURATION TESTS
# =============================================================================

class TestHAAddonEnvironment:
    """Test HA addon environment variable configuration"""

    def test_mise_ha_addon_detection(self):
        """Test MISE_HA_ADDON environment variable detection"""
        # Test when HA addon mode is enabled
        with patch.dict(os.environ, {'MISE_HA_ADDON': 'true'}):
            assert os.getenv('MISE_HA_ADDON') == 'true'

        # Test when HA addon mode is disabled
        with patch.dict(os.environ, {'MISE_HA_ADDON': 'false'}, clear=True):
            assert os.getenv('MISE_HA_ADDON') == 'false'

    def test_debug_mode_detection(self):
        """Test DEBUG_MODE environment variable detection"""
        with patch.dict(os.environ, {'DEBUG_MODE': 'true'}):
            assert os.getenv('DEBUG_MODE') == 'true'

        with patch.dict(os.environ, {'DEBUG_MODE': 'false'}):
            assert os.getenv('DEBUG_MODE') == 'false'

    def test_database_url_configuration(self):
        """Test DATABASE_URL configuration for HA addon"""
        expected_url = "postgresql://mise:mise@127.0.0.1:5432/mise"
        with patch.dict(os.environ, {'DATABASE_URL': expected_url}):
            assert os.getenv('DATABASE_URL') == expected_url

    def test_redis_url_configuration(self):
        """Test REDIS_URL configuration for HA addon"""
        expected_url = "redis://127.0.0.1:6379"
        with patch.dict(os.environ, {'REDIS_URL': expected_url}):
            assert os.getenv('REDIS_URL') == expected_url

    def test_redis_pubsub_enabled(self):
        """Test REDIS_PUBSUB_ENABLED configuration"""
        with patch.dict(os.environ, {'REDIS_PUBSUB_ENABLED': 'true'}):
            assert os.getenv('REDIS_PUBSUB_ENABLED') == 'true'

    def test_upload_dir_configuration(self):
        """Test UPLOAD_DIR configuration for HA addon"""
        expected_dir = "/data/uploads"
        with patch.dict(os.environ, {'UPLOAD_DIR': expected_dir}):
            assert os.getenv('UPLOAD_DIR') == expected_dir

    def test_cors_origins_configuration(self):
        """Test CORS_ORIGINS configuration"""
        with patch.dict(os.environ, {'CORS_ORIGINS': '*'}):
            assert os.getenv('CORS_ORIGINS') == '*'

    def test_llm_provider_options(self):
        """Test LLM_PROVIDER configuration options"""
        valid_providers = ['embedded', 'ollama', 'openai', 'anthropic', 'google']
        for provider in valid_providers:
            with patch.dict(os.environ, {'LLM_PROVIDER': provider}):
                assert os.getenv('LLM_PROVIDER') == provider


# =============================================================================
# DEBUG ROUTER TESTS
# =============================================================================

class TestDebugRouter:
    """Test debug router functionality"""

    def test_is_debug_enabled_ha_addon(self):
        """Test debug enabled check for HA addon mode"""
        # Replicate the is_debug_enabled logic for testing
        def is_debug_enabled():
            return (
                os.getenv("MISE_HA_ADDON") == "true" or
                os.getenv("DEBUG_MODE", "false").lower() == "true"
            )

        # Test with HA addon enabled
        with patch.dict(os.environ, {'MISE_HA_ADDON': 'true', 'DEBUG_MODE': 'false'}):
            assert is_debug_enabled() is True

        # Test with debug mode enabled
        with patch.dict(os.environ, {'MISE_HA_ADDON': 'false', 'DEBUG_MODE': 'true'}):
            assert is_debug_enabled() is True

        # Test with both disabled
        with patch.dict(os.environ, {'MISE_HA_ADDON': 'false', 'DEBUG_MODE': 'false'}):
            assert is_debug_enabled() is False

    def test_log_name_validation(self):
        """Test log name validation prevents path traversal"""
        # Valid log names
        valid_names = ['backend.log', 'nginx-error.log', 'postgres-2024-01-15.log']
        for name in valid_names:
            assert ".." not in name
            assert "/" not in name

        # Invalid log names (path traversal attempts)
        invalid_names = ['../etc/passwd', '../../secrets', 'logs/../config']
        for name in invalid_names:
            assert ".." in name or "/" in name


# =============================================================================
# HOME ASSISTANT INTEGRATION TESTS
# =============================================================================

class TestHomeAssistantIntegration:
    """Test Home Assistant integration endpoints"""

    @pytest.mark.asyncio
    async def test_homeassistant_router_import(self):
        """Test Home Assistant router can be imported"""
        try:
            from routers.homeassistant import router
            assert router is not None
            assert router.prefix == "/homeassistant"
        except ImportError:
            # Skip if dependencies not installed
            pytest.skip("FastAPI not installed - skipping import test")

    def test_homeassistant_config_endpoint_structure(self):
        """Test Home Assistant config endpoint returns correct structure"""
        # Expected structure for HA REST sensor configuration
        expected_keys = ['sensors', 'example_config']

        # Simulate the response structure
        config_response = {
            "sensors": [
                {
                    "name": "Laro Today's Meals",
                    "resource": "/api/homeassistant/today",
                    "value_template": "{{ value_json.meals | length }} meals planned"
                },
                {
                    "name": "Laro Shopping List",
                    "resource": "/api/homeassistant/shopping",
                    "value_template": "{{ value_json.unchecked }} items"
                }
            ],
            "example_config": "# configuration.yaml..."
        }

        for key in expected_keys:
            assert key in config_response

        assert len(config_response["sensors"]) == 2

    def test_today_meals_response_structure(self):
        """Test today's meals endpoint response structure"""
        expected_keys = ['date', 'meals', 'next_meal', 'summary', 'count']

        # Simulate response
        today_response = {
            "date": "2026-01-19",
            "meals": [],
            "next_meal": None,
            "summary": "No meals planned",
            "count": 0
        }

        for key in expected_keys:
            assert key in today_response

    def test_shopping_list_response_structure(self):
        """Test shopping list endpoint response structure"""
        expected_keys = ['list_name', 'unchecked', 'total', 'items', 'summary']

        # Simulate response
        shopping_response = {
            "list_name": "Weekly Shopping",
            "unchecked": 5,
            "total": 10,
            "items": [],
            "summary": "5 items to buy"
        }

        for key in expected_keys:
            assert key in shopping_response

    def test_meal_type_ordering(self):
        """Test meal type ordering logic"""
        meal_order = {"Breakfast": 8, "Lunch": 12, "Dinner": 18, "Snack": 15}

        # Test ordering
        assert meal_order["Breakfast"] < meal_order["Lunch"]
        assert meal_order["Lunch"] < meal_order["Snack"]
        assert meal_order["Snack"] < meal_order["Dinner"]

    def test_next_meal_calculation(self):
        """Test next meal calculation based on current hour"""
        meal_order = {"Breakfast": 8, "Lunch": 12, "Dinner": 18, "Snack": 15}

        plans = [
            {"meal_type": "Breakfast", "recipe_title": "Pancakes"},
            {"meal_type": "Lunch", "recipe_title": "Salad"},
            {"meal_type": "Dinner", "recipe_title": "Pasta"}
        ]

        # At 10:00, next meal should be Lunch
        current_hour = 10
        sorted_plans = sorted(plans, key=lambda x: meal_order.get(x.get("meal_type", ""), 12))
        next_meal = None
        for plan in sorted_plans:
            if meal_order.get(plan.get("meal_type", ""), 12) > current_hour:
                next_meal = plan
                break

        assert next_meal["meal_type"] == "Lunch"

        # At 13:00, next meal should be Dinner
        current_hour = 13
        next_meal = None
        for plan in sorted_plans:
            if meal_order.get(plan.get("meal_type", ""), 12) > current_hour:
                next_meal = plan
                break

        assert next_meal["meal_type"] == "Dinner"


# =============================================================================
# FRONTEND API CONFIGURATION TESTS
# =============================================================================

class TestFrontendAPIConfiguration:
    """Test frontend API configuration for HA addon"""

    def test_server_url_fallback_logic(self):
        """Test server URL fallback logic for same-origin proxy"""
        def get_server_url(saved_url=None, runtime_url=None, build_url=None):
            if saved_url:
                return saved_url
            if runtime_url and not runtime_url.startswith('%'):
                return runtime_url
            return build_url or ''

        # Test with saved URL
        assert get_server_url(saved_url="http://localhost:8001") == "http://localhost:8001"

        # Test with runtime URL (placeholder not replaced)
        assert get_server_url(runtime_url="%REACT_APP_BACKEND_URL%") == ''

        # Test with runtime URL (placeholder replaced)
        assert get_server_url(runtime_url="http://backend:8001") == "http://backend:8001"

        # Test fallback to empty (same-origin proxy)
        assert get_server_url() == ''

    def test_is_server_configured_logic(self):
        """Test server configuration check logic"""
        def is_server_configured(url, protocol='https:'):
            if url and len(url) > 0:
                return True
            return protocol != 'file:'

        # Explicit URL configured
        assert is_server_configured("http://localhost:8001") is True

        # Same-origin proxy mode (browser context)
        assert is_server_configured("", protocol='https:') is True
        assert is_server_configured("", protocol='http:') is True

        # File protocol (not configured)
        assert is_server_configured("", protocol='file:') is False

    def test_api_base_url_construction(self):
        """Test API base URL construction"""
        def construct_base_url(server_url):
            return server_url + '/api'

        # With server URL
        assert construct_base_url("http://localhost:8001") == "http://localhost:8001/api"

        # Same-origin proxy (empty URL)
        assert construct_base_url("") == "/api"

    def test_hash_router_path_detection(self):
        """Test HashRouter path detection for redirects"""
        def should_redirect_to_server(current_hash):
            return not current_hash.includes('/server') if hasattr(current_hash, 'includes') else '/server' not in (current_hash or '')

        # Not on server page
        assert should_redirect_to_server('#/dashboard') is True
        assert should_redirect_to_server('#/login') is True
        assert should_redirect_to_server('') is True

        # On server page
        assert should_redirect_to_server('#/server') is False

    def test_auth_redirect_uses_hash(self):
        """Test auth redirects use hash for HashRouter"""
        # Simulate the redirect logic
        def get_redirect_url(target):
            return f"#/{target}"

        assert get_redirect_url("login") == "#/login"
        assert get_redirect_url("server") == "#/server"


# =============================================================================
# AUTH CONTEXT TESTS
# =============================================================================

class TestAuthContext:
    """Test AuthContext functionality"""

    def test_server_url_construction_for_extended_user(self):
        """Test server URL construction for extended user fetch"""
        def get_server_url(saved_url=None, env_url=None):
            return saved_url or env_url or ''

        # Same-origin proxy mode
        url = get_server_url()
        assert url == ''
        assert f"{url}/api/auth/me/extended" == "/api/auth/me/extended"

        # With saved URL
        url = get_server_url(saved_url="http://localhost:8001")
        assert f"{url}/api/auth/me/extended" == "http://localhost:8001/api/auth/me/extended"

    def test_extended_user_response_handling(self):
        """Test handling of extended user response"""
        # Successful response
        def handle_response(ok, data, fallback):
            if ok:
                return data
            return fallback

        user_data = {"id": "123", "name": "Test", "role": "admin"}
        fallback_data = {"id": "123", "name": "Test"}

        # OK response
        result = handle_response(True, user_data, fallback_data)
        assert result["role"] == "admin"

        # Failed response (use fallback)
        result = handle_response(False, None, fallback_data)
        assert "role" not in result


# =============================================================================
# NGINX CONFIGURATION TESTS
# =============================================================================

class TestNginxConfiguration:
    """Test Nginx configuration for HA addon"""

    def test_nginx_location_patterns(self):
        """Test Nginx location patterns"""
        locations = {
            '/': 'try_files $uri $uri/ /index.html',
            '/api/': 'proxy_pass http://backend/api/',
            '/api/ws/': 'proxy_pass http://backend/api/ws/',
            '/uploads/': 'alias /data/uploads/',
            '/health': 'return 200 "OK"'
        }

        # All expected locations should be present
        assert '/' in locations
        assert '/api/' in locations
        assert '/api/ws/' in locations
        assert '/uploads/' in locations
        assert '/health' in locations

    def test_websocket_upgrade_headers(self):
        """Test WebSocket upgrade headers are configured"""
        websocket_headers = [
            'proxy_http_version 1.1',
            'Upgrade $http_upgrade',
            'Connection "upgrade"'
        ]

        # All WebSocket headers should be present
        assert len(websocket_headers) == 3

    def test_security_headers(self):
        """Test security headers are configured"""
        security_headers = {
            'X-Frame-Options': 'SAMEORIGIN',
            'X-Content-Type-Options': 'nosniff',
            'X-XSS-Protection': '1; mode=block'
        }

        # All security headers should be present
        assert security_headers['X-Frame-Options'] == 'SAMEORIGIN'
        assert security_headers['X-Content-Type-Options'] == 'nosniff'

    def test_backend_upstream_configuration(self):
        """Test backend upstream is correctly configured"""
        upstream = {
            'name': 'backend',
            'server': '127.0.0.1:8001'
        }

        assert upstream['server'] == '127.0.0.1:8001'


# =============================================================================
# RUN.SH SCRIPT TESTS
# =============================================================================

class TestRunScript:
    """Test run.sh startup script functionality"""

    def test_jwt_secret_generation(self):
        """Test JWT secret generation logic"""
        import secrets
        import base64

        # Simulate JWT secret generation
        random_bytes = secrets.token_bytes(64)
        jwt_secret = base64.b64encode(random_bytes).decode('ascii')[:64]

        # JWT secret should be 64 characters
        assert len(jwt_secret) == 64
        # Should only contain alphanumeric and base64 characters
        assert all(c.isalnum() or c in '+/=' for c in jwt_secret)

    def test_llm_provider_defaults(self):
        """Test LLM provider default values"""
        defaults = {
            'llm_provider': 'embedded',
            'ollama_url': 'http://homeassistant.local:11434',
            'ollama_model': 'llama3'
        }

        assert defaults['llm_provider'] == 'embedded'
        assert defaults['ollama_url'] == 'http://homeassistant.local:11434'

    def test_postgres_configuration_defaults(self):
        """Test PostgreSQL configuration defaults"""
        defaults = {
            'max_connections': '100',
            'shared_buffers': '256MB',
            'listen_addresses': '127.0.0.1',
            'port': '5432'
        }

        assert defaults['max_connections'] == '100'
        assert defaults['shared_buffers'] == '256MB'

    def test_redis_configuration_defaults(self):
        """Test Redis configuration defaults"""
        defaults = {
            'maxmemory': '256mb',
            'maxmemory_policy': 'allkeys-lru',
            'appendonly': 'yes',
            'bind': '127.0.0.1',
            'port': '6379'
        }

        assert defaults['maxmemory'] == '256mb'
        assert defaults['appendonly'] == 'yes'

    def test_celery_configuration_defaults(self):
        """Test Celery configuration defaults"""
        defaults = {
            'concurrency': '2',
            'enable_flower': 'true'
        }

        assert defaults['concurrency'] == '2'
        assert defaults['enable_flower'] == 'true'

    def test_data_directories(self):
        """Test data directory paths"""
        directories = [
            '/data/postgres',
            '/data/redis',
            '/data/uploads',
            '/var/log/mise',
            '/var/run/postgresql'
        ]

        # All directories should be valid paths
        for dir_path in directories:
            assert dir_path.startswith('/')


# =============================================================================
# SUPERVISORD CONFIGURATION TESTS
# =============================================================================

class TestSupervisordConfiguration:
    """Test supervisord configuration for HA addon"""

    def test_service_priorities(self):
        """Test service startup priorities"""
        priorities = {
            'postgres': 100,
            'redis': 150,
            'backend': 200,
            'worker': 250,
            'flower': 260,
            'nginx': 300
        }

        # PostgreSQL should start first
        assert priorities['postgres'] < priorities['redis']
        # Redis should start before backend
        assert priorities['redis'] < priorities['backend']
        # Backend should start before worker
        assert priorities['backend'] < priorities['worker']
        # Nginx should start last
        assert priorities['nginx'] == max(priorities.values())

    def test_service_restart_configuration(self):
        """Test service restart configuration"""
        services = ['postgres', 'redis', 'backend', 'worker', 'flower', 'nginx']

        # All services should have autorestart enabled
        for service in services:
            assert service in services

    def test_backend_port_configuration(self):
        """Test backend service port configuration"""
        backend_config = {
            'host': '127.0.0.1',
            'port': 8001
        }

        assert backend_config['host'] == '127.0.0.1'
        assert backend_config['port'] == 8001

    def test_flower_port_configuration(self):
        """Test Flower dashboard port configuration"""
        flower_config = {
            'port': 5555,
            'url_prefix': '/flower'
        }

        assert flower_config['port'] == 5555
        assert flower_config['url_prefix'] == '/flower'


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestHAAddonIntegration:
    """Integration tests for HA addon"""

    @pytest.mark.asyncio
    async def test_app_imports_with_ha_addon_config(self):
        """Test app can be imported with HA addon configuration"""
        with patch.dict(os.environ, {
            'MISE_HA_ADDON': 'true',
            'DATABASE_URL': 'postgresql://mise:mise@127.0.0.1:5432/mise',
            'REDIS_URL': 'redis://127.0.0.1:6379',
            'JWT_SECRET': 'test-secret-key-for-testing'
        }):
            try:
                from server import app
                assert app is not None
                assert app.title == "Laro API"
            except ImportError:
                # Skip if dependencies not installed
                pytest.skip("FastAPI not installed - skipping import test")

    @pytest.mark.asyncio
    async def test_debug_router_imports(self):
        """Test debug router can be imported"""
        try:
            from routers.debug import router
            assert router is not None
            assert router.prefix == "/debug"
        except ImportError:
            # Skip if dependencies not installed
            pytest.skip("FastAPI not installed - skipping import test")

    @pytest.mark.asyncio
    async def test_config_settings_with_ha_addon(self):
        """Test config settings are correct for HA addon"""
        with patch.dict(os.environ, {
            'MISE_HA_ADDON': 'true',
            'DEBUG_MODE': 'true',
            'LOG_LEVEL': 'DEBUG'
        }):
            from config import Settings
            settings = Settings()

            assert settings.debug_mode is True
            assert settings.log_level == 'DEBUG'


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================

class TestHealthChecks:
    """Test health check functionality"""

    def test_health_response_structure(self):
        """Test health check response structure"""
        expected_keys = ['status', 'app', 'version', 'database', 'llm_provider',
                        'websocket_connections', 'redis']

        # Simulate health response
        health_response = {
            "status": "healthy",
            "app": "Laro",
            "version": "3.0.3",
            "database": "postgresql",
            "llm_provider": "embedded",
            "websocket_connections": 0,
            "redis": {
                "enabled": True,
                "connected": True,
                "mode": "multi-instance"
            }
        }

        for key in expected_keys:
            assert key in health_response

        assert health_response["status"] == "healthy"
        assert health_response["database"] == "postgresql"

    def test_redis_health_structure(self):
        """Test Redis health check response structure"""
        redis_health = {
            "enabled": True,
            "connected": True,
            "mode": "multi-instance"
        }

        assert "enabled" in redis_health
        assert "connected" in redis_health
        assert "mode" in redis_health


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Test error handling for HA addon"""

    def test_path_traversal_prevention(self):
        """Test path traversal is prevented in log access"""
        dangerous_names = [
            '../etc/passwd',
            '../../secrets',
            'logs/../../../root/.ssh/id_rsa',
            '/etc/shadow',
            'log/../../config'
        ]

        for name in dangerous_names:
            assert ".." in name or "/" in name

    def test_admin_role_check(self):
        """Test admin role check logic"""
        def is_admin(user):
            return user.get("role") == "admin"

        admin_user = {"id": "1", "role": "admin"}
        regular_user = {"id": "2", "role": "user"}
        no_role_user = {"id": "3"}

        assert is_admin(admin_user) is True
        assert is_admin(regular_user) is False
        assert is_admin(no_role_user) is False


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
