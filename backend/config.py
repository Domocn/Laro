import os
from pathlib import Path


def _get_version() -> str:
    """Get version from VERSION file or environment variable."""
    # First check environment variable (set during Docker build)
    env_version = os.getenv("APP_VERSION")
    if env_version:
        return env_version.strip()

    # Try to read from VERSION file (development or local deployment)
    version_paths = [
        Path(__file__).parent.parent / "VERSION",  # ../VERSION from backend/
        Path(__file__).parent / "VERSION",          # VERSION in backend/
        Path("/app/VERSION"),                       # Docker container path
    ]

    for version_path in version_paths:
        if version_path.exists():
            return version_path.read_text().strip()

    return "0.0.0-dev"


class Settings:
    def __init__(self):
        # Application version (from VERSION file or environment)
        self.version: str = _get_version()

        # PostgreSQL database settings
        self.database_url: str = os.getenv("DATABASE_URL", "postgresql://mise:mise@localhost:5432/mise")

        # JWT_SECRET must be set in production - generate with: openssl rand -base64 32
        jwt_secret = os.getenv("JWT_SECRET")
        if not jwt_secret:
            import warnings
            warnings.warn(
                "JWT_SECRET not set! Using insecure default. "
                "Set JWT_SECRET environment variable in production.",
                RuntimeWarning
            )
            jwt_secret = "INSECURE_DEFAULT_CHANGE_ME_IN_PRODUCTION"
        self.jwt_secret: str = jwt_secret
        self.jwt_algorithm: str = "HS256"

        self.llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")
        self.ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3")
        self.openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
        self.groq_api_key: str | None = os.getenv("GROQ_API_KEY")
        self.groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        self.cors_origins: str = os.getenv("CORS_ORIGINS", "*")

        self.upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")
        
        # OAuth Settings (configure to enable)
        self.google_client_id: str | None = os.getenv("GOOGLE_CLIENT_ID")
        self.google_client_secret: str | None = os.getenv("GOOGLE_CLIENT_SECRET")
        self.github_client_id: str | None = os.getenv("GITHUB_CLIENT_ID")
        self.github_client_secret: str | None = os.getenv("GITHUB_CLIENT_SECRET")
        self.oauth_redirect_base_url: str = os.getenv("OAUTH_REDIRECT_BASE_URL", "http://localhost:3001")
        
        # Email Settings (configure to enable password reset emails)
        self.email_enabled: bool = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
        self.smtp_host: str | None = os.getenv("SMTP_HOST")
        self.smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user: str | None = os.getenv("SMTP_USER")
        self.smtp_password: str | None = os.getenv("SMTP_PASSWORD")
        self.smtp_from_email: str | None = os.getenv("SMTP_FROM_EMAIL")
        
        # Resend API (alternative to SMTP)
        self.resend_api_key: str | None = os.getenv("RESEND_API_KEY")

        # Static frontend serving (for combined Docker image)
        self.serve_frontend: bool = os.getenv("SERVE_FRONTEND", "false").lower() == "true"
        self.static_files_dir: str = os.getenv("STATIC_FILES_DIR", "static")

        # Cloud deployment flag - when True, AI is managed by the service (GPT4All)
        # Self-hosted users can choose their own AI provider
        self.is_cloud: bool = os.getenv("IS_CLOUD", "false").lower() == "true"

        # Redis Settings (for Pub/Sub and caching)
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_pubsub_enabled: bool = os.getenv("REDIS_PUBSUB_ENABLED", "true").lower() == "true"

        # Supabase Settings (for auth)
        self.supabase_url: str | None = os.getenv("SUPABASE_URL")
        self.supabase_jwt_secret: str | None = os.getenv("SUPABASE_JWT_SECRET")
        self.supabase_anon_key: str | None = os.getenv("SUPABASE_ANON_KEY")
        self.supabase_service_key: str | None = os.getenv("SUPABASE_SERVICE_KEY")

        # Debug Settings (default false for security, set DEBUG_MODE=true for development)
        self.debug_mode: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.debug_level: str = os.getenv("DEBUG_LEVEL", "INFO")
        self.debug_log_requests: bool = os.getenv("DEBUG_LOG_REQUESTS", "true").lower() == "true"
        self.debug_log_db_queries: bool = os.getenv("DEBUG_LOG_DB_QUERIES", "false").lower() == "true"
        self.debug_log_websockets: bool = os.getenv("DEBUG_LOG_WEBSOCKETS", "false").lower() == "true"
        self.debug_log_auth: bool = os.getenv("DEBUG_LOG_AUTH", "true").lower() == "true"
        self.debug_log_ai: bool = os.getenv("DEBUG_LOG_AI", "true").lower() == "true"

    def get_debug_config(self) -> dict:
        """Get all debug-related configuration for diagnostics."""
        return {
            "debug_mode": self.debug_mode,
            "log_level": self.log_level,
            "debug_level": self.debug_level,
            "debug_log_requests": self.debug_log_requests,
            "debug_log_db_queries": self.debug_log_db_queries,
            "debug_log_websockets": self.debug_log_websockets,
            "debug_log_auth": self.debug_log_auth,
            "debug_log_ai": self.debug_log_ai,
        }

settings = Settings()
