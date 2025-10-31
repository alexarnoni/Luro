from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./luro.db"
    
    # Application
    SECRET_KEY: str = "change-this-secret-key-in-production"
    APP_NAME: str = "Luro"
    DEBUG: bool = True
    
    # Resend API
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "noreply@example.com"
    
    # Magic Link
    MAGIC_LINK_EXPIRY_MINUTES: int = 15
    
    class Config:
        env_file = ".env"


settings = Settings()
