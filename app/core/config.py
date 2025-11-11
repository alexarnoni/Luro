from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./luro.db"

    # Application
    ENV: str = "development"
    SECRET_KEY: str = "change-this-secret-key-in-production"
    APP_NAME: str = "Luro"
    DEBUG: bool = True
    ENABLE_CSRF_JSON: bool = True

    # Resend API
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "noreply@example.com"

    # Magic Link
    MAGIC_LINK_EXPIRY_MINUTES: int = 15

    # Security
    RATE_LIMIT_MAX: int = 5
    RATE_LIMIT_WINDOW_SECONDS: int = 15 * 60
    IMPORT_MAX_FILE_MB: int = 5

    # AI Providers
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-mini"
    INSIGHTS_MAX_PER_MONTH: int = 5
    
    class Config:
        env_file = ".env"


settings = Settings()
