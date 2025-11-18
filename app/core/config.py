from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./luro.db"
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "testserver"]

    # Application
    ENV: str = "development"
    SECRET_KEY: str = "change-this-secret-key-in-production"
    APP_NAME: str = "Luro"
    DEBUG: bool = True
    ENABLE_CSRF_JSON: bool = True
    ENABLE_SECURITY_HARDENING: bool = False
    LOG_LEVEL: str = "INFO"

    # Resend API
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "noreply@example.com"

    # Captcha
    TURNSTILE_SITE_KEY: str = ""
    TURNSTILE_SECRET_KEY: str = ""

    # Magic Link
    MAGIC_LINK_EXPIRY_MINUTES: int = 15
    LOGIN_RATE_LIMIT_IP_MAX: int = 10
    LOGIN_RATE_LIMIT_IP_WINDOW_SECONDS: int = 10 * 60
    LOGIN_RATE_LIMIT_EMAIL_MAX: int = 5
    LOGIN_RATE_LIMIT_EMAIL_WINDOW_SECONDS: int = 60 * 60

    # Security
    RATE_LIMIT_MAX: int = 5
    RATE_LIMIT_WINDOW_SECONDS: int = 15 * 60
    IMPORT_MAX_FILE_MB: int = 5

    # Static assets cache busting
    ASSETS_VERSION: str = "1"

    # AI Providers
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-mini"
    INSIGHTS_MAX_PER_MONTH: int = 5

    # Pydantic v2 compatible settings: read .env and ignore extra env vars
    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()


def _validate_security() -> None:
    """Fail fast when running production with insecure defaults."""
    env = settings.ENV.lower()
    if env != "production":
        return

    if settings.SECRET_KEY == "change-this-secret-key-in-production":
        raise ValueError("SECRET_KEY must be set to a strong value in production.")

    if settings.DATABASE_URL.startswith("sqlite"):
        raise ValueError("Use PostgreSQL in production; sqlite is only for local/dev.")


_validate_security()
