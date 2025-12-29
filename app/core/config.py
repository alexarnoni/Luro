from typing import Any

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
DEFAULT_SECRET_KEY = "change-this-secret-key-in-production"


def _normalize_allowed_hosts(value: Any) -> list[str]:
    """Accept comma-separated string or list-like and normalize hosts."""
    if value is None or value == "":
        return []

    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        parts = [str(part).strip() for part in value]
    else:
        return []

    return [part for part in parts if part]


def _normalize_admin_emails(value: Any) -> list[str]:
    """Accept comma-separated string or list-like and normalize to lowercase."""
    if value is None or value == "":
        return []

    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        parts = [str(part).strip() for part in value]
    else:
        return []

    return [part.lower() for part in parts if part]


class Settings(BaseSettings):
    """Application settings."""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./luro.db"
    ALLOWED_HOSTS: list[str] = Field(default_factory=lambda: DEFAULT_ALLOWED_HOSTS.copy())

    # Application
    ENV: str = "development"
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    APP_NAME: str = "Luro"
    DEBUG: bool = True
    ENABLE_CSRF_JSON: bool = True
    ENABLE_SECURITY_HARDENING: bool = False
    LOG_LEVEL: str = "INFO"

    # Resend API
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "noreply@example.com"
    FEEDBACK_TO_EMAIL: str = "alexandre.anf@gmail.com"

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
    ADMIN_EMAILS_RAW: str = Field(default="", alias="ADMIN_EMAILS")

    # Static assets cache busting
    ASSETS_VERSION: str = "4"

    # AI Providers
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-mini"
    OLLAMA_URL: str = "http://ollama:11434/api/generate"
    OLLAMA_MODEL: str = "phi3"
    INSIGHTS_MAX_PER_MONTH: int = 5

    # Pydantic v2 compatible settings: read .env and ignore extra env vars
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value: Any) -> list[str] | Any:
        """Support comma-separated ALLOWED_HOSTS from environment."""
        return _normalize_allowed_hosts(value)

    @computed_field
    @property
    def admin_emails(self) -> list[str]:
        """Return normalized admin emails list from raw env input."""
        return _normalize_admin_emails(self.ADMIN_EMAILS_RAW)


def _validate_security() -> None:
    """Fail fast when running production with insecure defaults."""
    env = settings.ENV.lower()
    if env != "production":
        return

    secret = settings.SECRET_KEY
    if not secret or secret == DEFAULT_SECRET_KEY or len(secret) < 32:
        raise ValueError("SECRET_KEY must be set to a strong value in production.")

    if not settings.ALLOWED_HOSTS or settings.ALLOWED_HOSTS == DEFAULT_ALLOWED_HOSTS:
        raise ValueError("ALLOWED_HOSTS must be configured explicitly in production.")

    if settings.DATABASE_URL.startswith("sqlite"):
        raise ValueError("Use PostgreSQL in production; sqlite is only for local/dev.")


settings = Settings()


_validate_security()
